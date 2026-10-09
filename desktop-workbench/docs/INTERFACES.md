# 命令、状态与自动化测试

`project.json`保存非秘密项目配置、命令目录和用例。模型密钥只保存到当前Windows用户的DPAPI保险库，不写入项目、报告或导出包。

函数命令示例：

```json
{"id":"apply","label":"作者的操作","function":"Apply","params":[{"name":"amount","type":"integer","default":1}]}
```

GUI入口使用 `entry_kind:"trigger"`、`trigger:"gg_trg_Apply"` 与对应动作函数名 `function:"Trig_Apply_Actions"`，参数列表为空。程序执行TriggerEvaluate，再按条件执行TriggerExecute；需要GetTriggerUnit等事件上下文的入口会拒绝直接接入。

观测字段示例：

```json
{"id":"count","label":"次数","type":"integer","source":"global","name":"udg_Count"}
```

固定数组索引增加 `index:0`。可选 `source` 为global/gold/lumber/ticks，后者不需要name。不存在的变量、数组类型或函数签名变化使构建失败。

用例示例：

```json
{
  "id":"author_case","name":"作者定义的行为","tags":[],
  "steps":[
    {"type":"command","op":"snapshot","save_as":"before"},
    {"type":"command","op":"apply","args":{"amount":1},"request_id":"operation_a"},
    {"type":"wait","path":"last.count","operator":"eq","ref":"before.count","offset":1,"timeout":15},
    {"type":"command","op":"apply","args":{"amount":1},"request_id":"operation_a"},
    {"type":"command","op":"snapshot"},
    {"type":"assert","path":"last.count","operator":"eq","ref":"before.count","offset":1}
  ]
}
```

每次运行把去重别名转换成本批次的新请求ID；同一用例中相同别名沿用同ID。要测试业务重复处理，省略别名或使用不同别名。

命令响应的result保存为指定名称，并同时更新last；等待步骤持续读取snapshot更新last。比较为eq/ne/gt/ge/lt/le/exists。等待最多120秒。状态路径和比较都是声明式规则，不执行任意Python表达式。

每个项目和每次会话独立；桥校验session/build/id。请求超时仍保留原身份。业务分发、业务结算、条件观测与清理分开判断。报告含每步响应、实际与预期、耗时、失败步骤以及所属进程收尾结果；自动生成HTML摘要。

AI可用只读检索只有search_functions/read_functions/search_globals；最终输出固定映射和用例。执行方生成桥代码，模型不能发送任意Shell或运行任意游戏脚本。每轮5请求、最多3轮接入修复。首次发送源码需要用户选择相应范围；模型调用使用用户自己的账户。
main/config及桥内部函数不能注册为业务命令；含脚本解释或动态函数调用的字符串参数入口也拒绝暴露。需要此类内部实现的地图应提供固定业务标识的包装入口。

GUI地图使用已保存运行脚本，保留WTG/WCT，不宣称读取编辑器未保存内容。源码构建只在隔离副本调用作者登记的参数数组，要求输出完整JASS。作者构建链、依赖与资源仍由项目提供。
