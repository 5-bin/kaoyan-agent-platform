"""Explicit synthetic vectors for HTTP/browser tests, never a production encoder."""
class ContractEncoder:
    def encode(self, texts):
        topics = ('二叉树', 'TCP', 'UDP', '堆', '队列', '进程', '内存', '线性表')
        result = []
        for text in texts:
            vector = [0.] * (len(topics) + 1)
            for i, topic in enumerate(topics):
                if topic in text or i == 0 and ('左右孩子' in text or '至多两个分支' in text):
                    vector[i] = 1.
            if not any(vector):
                vector[-1] = 1.
            result.append(vector)
        return result
