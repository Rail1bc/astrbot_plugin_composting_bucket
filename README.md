#  CompostingBucket - DeepSeek API的专用堆肥桶

> 简单逻辑
>
> 让deepseek api调用费用更低！
---
### 硬盘缓存，计费降低到原本的约四分之一！
 
> 在角色扮演互动的场景中，会产生大量的历史消息上下文，每次新的请求都会携带这些内容
>
> 对话越长，消耗的token数量也越多
> 
> 角色扮演互动中，历史上下文占token消耗的绝大部分
> 
> 但是DeepSeek api提供硬盘缓存服务，命中缓存的token计费将是未命中的四分之一！

 - DeepSeek API 创新采用硬盘缓存，价格再降一个数量级：
   - https://api-docs.deepseek.com/zh-cn/news/news0802
 - 上下文硬盘缓存
   - https://api-docs.deepseek.com/zh-cn/guides/kv_cache
 
> 最美妙的是，这项服务不需要你做任何事！
> 
> 只需要正常使用，默认开启！
---

## 命中缓存并非必定触发
 - 只有当两个请求的前缀内容相同时（从第 0 个 token 开始相同），才算重复。中间开始的重复不能被缓存命中。
 - DeepSeek API 最大上下文长度 64K
> 一些情况，会导致命中缓存这一机制几乎完全失效！
 - 每次请求使用不一样的提示词
   - AstrBot WebUI -> 配置文件 -> 服务提供商 -> 大语言模型设置 -> 启用日期时间系统提示
> 启用日期时间系统提示，会在系统提示词中加上当前机器的日期时间
> 
> 这会导致每次请求，上下文从此处开始不再一致
> 
> 将只有系统提示词的内容会命中缓存，携带的所有历史消息都不会命中缓存！
 - 从起始处变化的历史上下文
   - AstrBot WebUI -> 配置文件 -> 服务提供商 -> 大语言模型设置 -> 最多携带对话数量(条)
> 当对话数量超过这项配置，会逐渐丢弃最旧的对话
> 
> 同上，这也会导致上下文从此处开始不再一致
> 
> 即使设置为 -1 不限制最大条数也会导致类似的问题
> 
> 因为 DeepSeek API 存在最大可处理上下文长度
---

## 堆肥桶做了什么?
 - 堆肥桶主要解决的问题是
> 当对话消息达到 最多携带对话数量(条) 配置时
>
> 每次新请求，历史上下文都会有一个新的起始
    
 - 堆肥桶的处理方式是:
> 当历史对话消息数量达到 堆肥桶容量 (max_len)  时 
>
> 清除最旧的 排出消息量 (pop_len) 条
>
> 这样，命中缓存机制将仅在排出旧消息后，失效1次

## 使用建议
 - 必须遵循的规则
   - 堆肥桶容量 (max_len) 必须小于 最多携带对话数量(条)
   - 排出消息量 (pop_len) 必须小于 堆肥桶容量 (max_len)
 - 建议
   - 建议配合 长期记忆 插件一起使用
     - https://github.com/lxfight/astrbot_plugin_mnemosyne
   - 排出消息量 (pop_len) 不宜过于接近 堆肥桶容量 (max_len) 
     - 这会导致保留的上下文过少，影响互动质量