"""Apply the authorized OSS config and verify storage before reopening the API."""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

from oss_smoke import exercise

SPEC = importlib.util.spec_from_file_location('oss_upgrade_base',Path(__file__).with_name('upgrade-server-release.py'))
upgrade = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = upgrade
SPEC.loader.exec_module(upgrade)


class OssUpgrade(upgrade.Upgrade):
    """Restore environment before old services restart on any switch failure."""

    config_file: Path
    config_output: Path
    credentials: Path

    def restore_environment(self) -> None:
        """Use the backed-up config preimage, refusing concurrent env changes."""
        result = subprocess.run([sys.executable,str(Path(__file__).with_name('configure-server-oss.py')),'--output',str(self.config_output),'--restore','--apply'],capture_output=True,text=True,timeout=30)
        upgrade.require(result.returncode==0,'环境恢复失败，保留维护状态及备份')

    def rollback(self) -> None:
        """Restore secrets/config while maintenance still protects the old version."""
        self.restore_environment()
        super().rollback()

    def start(self) -> None:
        """Check real scoped OSS uploads and cleanup before reopening public APIs."""
        super().start()
        exercise(self.db,self.credentials,self.output,self.config_file)
        self.state['ossVerified'] = True


def main() -> None:
    """Validate first; require explicit activation for configuration and service writes."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('current-release','release-root','rehearsal','data-helper','manifest','output','config','config-output','credentials'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--expected-plan',required=True)
    parser.add_argument('--expected-manifest',required=True)
    parser.add_argument('--activate',action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    obj = OssUpgrade(args.release_root.resolve(),args.rehearsal.resolve(),args.data_helper.resolve(),args.expected_plan,args.output,False,False,upgrade.base.System(args.output),current=args.current_release.resolve(),manifest=args.manifest.resolve(),expected_manifest=args.expected_manifest)
    obj.config_file=args.config
    obj.config_output=args.config_output
    obj.credentials=args.credentials
    config_command=[sys.executable,str(Path(__file__).with_name('configure-server-oss.py')),'--config',str(args.config),'--output',str(args.config_output)]
    if not args.activate:
        subprocess.run(config_command,check=True,timeout=30)
        print(obj.validate(),flush=True)
        return
    with upgrade.deployment_lock(Path('/run/lock/kaoyan-upgrade.lock')):
        try:
            subprocess.run(config_command+['--apply'],check=True,timeout=30)
            print(obj.validate(),flush=True)
            obj.activate()
        except BaseException:
            if (args.config_output/'config-result.json').exists():
                obj.restore_environment()
            raise


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(str(error) if isinstance(error,RuntimeError) else 'OSS发布失败，异常类别='+type(error).__name__) from None
