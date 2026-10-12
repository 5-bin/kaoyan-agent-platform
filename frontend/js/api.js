/** 同源请求入口；令牌由调用者提供，服务端决定记录归属。 */
export async function request(path, { token = "", ...options } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 55000);
  const headers = { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  try {
    const response = await fetch(path, { ...options, headers, signal: controller.signal });
    const text = await response.text();
    let data;
    try { data = text ? JSON.parse(text) : null; } catch { throw new Error("服务返回格式异常，请稍后重试"); }
    if (!response.ok) {
      const error = new Error(data?.message || `请求失败（${response.status}）`);
      error.status = response.status; error.code = data?.code; throw error;
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("等待超时。任务可能仍在处理，请先刷新学习记录，不要立即重复提交。");
    if (error instanceof TypeError) throw new Error("无法连接服务，请检查网络后重试");
    throw error;
  } finally { clearTimeout(timer); }
}
