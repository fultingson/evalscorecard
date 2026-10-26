# evalscorecard

**把评测结果压成一张能对比的记分卡。**

`evalscorecard` —— 把多次评测的样本级结果聚合成记分卡，逐指标列出均值、离散度与回归项。

- 零依赖，Python 3.10+ 标准库即可运行
- 单文件，`evalscorecard.py` 拷走就能用
- 不联网、不写文件

<!-- ipos:install -->
## 安装

零依赖，Python 3.10+ 即可：

```bash
pip install fultingson-evalscorecard
```

装完直接用命令名调用：

```bash
evalscorecard --help
```

也可以不用安装，直接把 `evalscorecard.py` 拷走用——它只依赖标准库。

## 为什么需要它

常见评测只报一个总分；evalscorecard 保留指标级方差与回归项，能看出总分没动但分布已经变了。

它遵守下面几条自己定的规矩：

1. **总分不动，不代表模型没变**。总分把涨和跌抵消掉了，所以必须保留指标级明细。
2. **离散度要一起看**。均值一样的两个模型，稳定性可能差很多。
3. **回归项排在最前**。哪个指标掉了，比掉了多少更重要。

## 用法

```bash
python evalscorecard.py --current run2.json --baseline run1.json
python evalscorecard.py --current run2.json --json
```

加 `--json` 可以拿到机器可读的结果，便于接到流水线里。

## 已知局限

- 只做两轮结果的对比，不负责跑评测。
- 指标方向默认「越大越好」，需要你自己标 lower_is_better。
- 不做加权总分之外的综合打分——总分会把涨和跌抵消掉。

## 跑测试

```bash
python test_evalscorecard.py
```

测试用独立的断言与临时数据，不污染工作目录。

## 来源与参考

- Python 标准库文档：<https://docs.python.org/3/>
- GitHub 仓库：<https://github.com/fultingson/evalscorecard>

---

## 关于作者

fultingson 做评测结果的统计读法相关的问题。这个工具先替你回答一个具体问题，再谈别的。

- 个人主页：<https://fultingson.github.io>
- 仓库：<https://github.com/fultingson/evalscorecard>

## 许可

MIT，见 [LICENSE](LICENSE)。
