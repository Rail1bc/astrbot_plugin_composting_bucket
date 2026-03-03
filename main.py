from copy import deepcopy

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.core.log import LogManager
from astrbot.core.utils.astrbot_path import get_astrbot_data_path
from database import CompostingBucketDB


@register("CompostingBucket", "Rail1bc", "一个用于收集被 “丢弃/压缩” 的上下文的插件", "0.2")
class MyPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.logger = LogManager.GetLogger(log_name="CompostingBucket")
        self.plugin_data_path = get_astrbot_data_path() / "plugin_data" / self.name
        self.db = CompostingBucketDB(self.plugin_data_path)

    @filter.on_llm_request()
    async def query_memory(self, event: AstrMessageEvent, req: ProviderRequest):
        """在 LLM 请求前检查上下文长度，必要时先收集最旧上下文再弹出。"""
        await self.check_message_length(event, req)

    async def check_message_length(self, event: AstrMessageEvent, req: ProviderRequest):
        max_len, pop_len = self._read_session_context_policy(event)
        if max_len <= 0 or pop_len <= 0:
            return

        # 历史上下文一般按 user/assistant 成对增长，这里按框架的 turn 语义转成消息条数。
        if len(req.contexts) >= max_len * 2:
            self.logger.info(
                "会话上下文长度达到阈值: max_context_length=%s, dequeue_context_length=%s",
                max_len,
                pop_len,
            )
            await self.pop_messages(event, req, pop_len)

    async def pop_messages(
        self,
        event: AstrMessageEvent,
        req: ProviderRequest,
        pop_len: int,
    ):
        pop_count = min(len(req.contexts), pop_len * 2)
        if pop_count <= 0:
            return

        # 在真正删除前采样最旧上下文。
        oldest_contexts = deepcopy(req.contexts[:pop_count])
        payload = {
            "reason": "plugin_pop",
            "pop_count": pop_count,
            "contexts": oldest_contexts,
        }

        bucket = event.get_extra("composting_bucket_collected_contexts", [])
        if not isinstance(bucket, list):
            bucket = []
        bucket.append(payload)
        event.set_extra("composting_bucket_collected_contexts", bucket)

        self.logger.info("处理 %s 条旧消息，已在删除前完成采样", pop_count)
        del req.contexts[:pop_count]

    def _read_session_context_policy(self, event: AstrMessageEvent) -> tuple[int, int]:
        cfg = self.context.get_config(umo=event.unified_msg_origin) or {}
        provider_settings = cfg.get("provider_settings", {})

        max_len_raw = provider_settings.get("max_context_length", -1)
        pop_len_raw = provider_settings.get("dequeue_context_length", 1)

        try:
            max_len = int(max_len_raw)
        except (TypeError, ValueError):
            max_len = -1

        try:
            pop_len = int(pop_len_raw)
        except (TypeError, ValueError):
            pop_len = 1

        return max_len, max(1, pop_len)
