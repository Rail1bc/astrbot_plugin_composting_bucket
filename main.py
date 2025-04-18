from distutils.command.check import check

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.core.log import LogManager
from astrbot.api.provider import ProviderRequest

from typing import List, Dict

@register("CompostingBucket", "Rail1bc", "一个用于降低AstrBot的deepseek api调用费用的插件", "0.1")
class MyPlugin(Star):
    def __init__(self, context: Context , config:dict ):
        super().__init__(context)
        self.config = config
        self.logger = LogManager.GetLogger(log_name="CompostingBucket")

    # --- 事件钩子 ---
    @filter.on_llm_request()
    async def query_memory(self, event: AstrMessageEvent, req: ProviderRequest):
        """[事件钩子] 在 LLM 请求前，检查历史上下文长度并处理"""
        await self.check_message_length(req)

    # 检查消息长度
    async def check_message_length(self, req: ProviderRequest):
        # self.logger.info("检查消息上下文长度,当前长度:" + str(len(req.contexts)))
        if(len(req.contexts) >= self.config.max_len*2):
            self.logger.info("消息上下文长度到达配置标准:" + str(self.config.max_len) + ",开始弹出旧消息")
            await self.pop_messages(req)

    # 弹出上下文历史中的旧消息
    async def pop_messages(self ,req: ProviderRequest):
        self.logger.info("处理" + str(self.config.pop_len) + "条旧消息")
        del req.contexts[:self.config.pop_len*2]



    # --- 插件生命周期方法 ---
    async def terminate(self):
        '''可选择实现 terminate 函数，当插件被卸载/停用时会调用。'''
