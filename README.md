## 深空之眼文件工具 

一个使用 Python的文件分析脚本，其中LuaJIT 工具的原理来自 https://github.com/unk35h/TextDumpScripts\_ag



## 主要功能

- 数据对比: 对比新旧版本，找出变更的内容。

- 目录浏览器: 加载资源路径树。

- 内置工具:

	- UnityFS 抹除工具: 从文件中抹除 UnityFS 文件头前的空字节。

	- LuaJIT 工具: 处理 LuaJIT 字节码。可用反编译LuaJIT。



## 安装与运行



1.  安装依赖

确保你已安装 Python。然后通过 pip 安装必要的库：

 ```bash

pip install -r requirements.txt

 ```

ljd来自 https://github.com/AzurLaneTools/ljd



2.  运行程序

打开main.py即可运行。
https://github.com/fengye-xiye/Aether-Gazer-Asset-Tool/blob/main/main.jpg



脚本本部分功能和优化是AI写的，可能会出奇怪的问题，但整体应该是能用的（）
LuaJIT处理会报错，但文件处理应该是完成的



## 许可证 (License)



本项目基于GNU General Public License v3.0协议开源。详情请见 \[LICENSE](LICENSE) 文件。





