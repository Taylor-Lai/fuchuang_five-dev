# Any2table

## 一、任务要求：

必须包含以下三个关键模块：

（1）文档智能操作交互模块：基于自然语言处理与文档结构理解技术，能够将用户对文档的编辑、排版、格式调整、内容提取等操作需求，通过自然语言指令进行解析与转化，自动执行相应操作。

> 可能类似于：https://www.open-notebook.ai/，或许用GUI agent

（2）非结构化文档信息提取模块：基于桌面端、Web网站或第三方平台部署，可以自动识别用户导入非结构化文档，然后利用人工智能或其他方式提取文件文本关键信息、实体数据或用户指定内容，进行数据库存储操作。充分实现功能，且不存在数据识别误差。

（3）表格自定义数据填写模块：利用脚本语句或人工智能等操作，在用户提供的表格和非结构化数据后，从非结构化数据中自动搜索相关信息并进行表格填写。

输入数据：根据四类文档来填写表格：docx、md、xlsx、txt 

优先完成（2）和（3），因为流程较为统一

## 二、初步方案

> 一个很影响精确度的核心点：**智能取数**和**智能计算**

一、存储阶段

采取一些解析库，来解析docx、xlsx（这两个需要收取数据填表）、txt（里面是用户需求） 

> 或者把docx和xlsx用工具转为md，这样或许便于处理

我建议以json为中间存储形式，然后图片存储为路径

为了加入一点创新点，用kggen库来提取kg

【待讨论：think on graph、还是做RAG，或者调整KG，因为kg偏向于关系一些】

二、填表阶段

1、引入agent skill，agent编排采用langchain和langgraph

2、多智能体设计：

（1）master：中枢节点，起到路由效果

（2）table agent：1、负责读取待填表格的表头schema，交付给master 2、负责填表

（3）RAG agent：再kg或者rag上做检索增强

（4）coder agent：用python代码来提高计算准确性

（5）verifier agent：做幻觉检测和反思

3、考虑一些智能取数、智能表格、智能文档、表格大模型的东西，和任务较为适配

## 数据格式：

在test_data中，待填表格可能是xlsx或者docx中的表格。都是按行填，且几乎都是数值

例如

![image-20260321010311589](C:\Users\blu\AppData\Roaming\Typora\typora-user-images\image-20260321010311589.png)

![image-20260321010339180](C:\Users\blu\AppData\Roaming\Typora\typora-user-images\image-20260321010339180.png)

![image-20260321010412617](C:\Users\blu\AppData\Roaming\Typora\typora-user-images\image-20260321010412617.png)