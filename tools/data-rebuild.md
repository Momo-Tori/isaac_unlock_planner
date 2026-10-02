# 数据重建与发布维护

本文说明如何从灰机 Wiki 保存页与 EID 数据重建项目数据、维护推荐配置，以及生成发布文件。所有命令均在项目根目录执行。

## 1. 准备环境与输入

需要 Python 3.10 或更新版本，以及矩阵解析使用的 BeautifulSoup：

```bash
python -m pip install beautifulsoup4
```

准备两份完整的 HTML 保存页。下文用 `temp/completion.html` 和 `temp/achievements.html` 作为示例路径，执行时替换成实际文件名。

| 输入 | 来源 | 用途 |
|---|---|---|
| `temp/completion.html` | [Project:存档/成就](https://isaac.huijiwiki.com/wiki/Project:%E5%AD%98%E6%A1%A3/%E6%88%90%E5%B0%B1) | 角色/Boss 通关标记矩阵、挑战与成就的对应关系 |
| `temp/achievements.html` | [成就](https://isaac.huijiwiki.com/wiki/%E6%88%90%E5%B0%B1) | 奖励实体链接、成就名称、解锁条件 |
| EID 中英文语言包 | 构建脚本内配置的 External Item Descriptions 地址 | 按实体类型和 ID 获取英文名、中文名及效果 |

EID 语言包缓存在 `tools/cache/eid/`。默认复用缓存，缺失时下载；刷新参数会重新下载。最终网页只读取构建好的本地文件，不在运行时抓取 Wiki 或 EID。

## 2. 完整重建

日常更新游戏数据时，优先使用统一入口：

```bash
python tools/rebuild_data.py "temp/completion.html" --achievements-html "temp/achievements.html"
```

需要同时刷新 EID 时，在命令末尾加 `--refresh-eid`。

完整流程按以下顺序执行：

1. 从两份 HTML 和 EID 英文包生成 `tools/achievement_rewards_en.json`。
2. 英文奖励生成成功后，删除原有的六个下游生成文件。
3. 重建角色/Boss 数据、挑战数据、中文效果及报告、其他成就数据。
4. 校验推荐配置，生成浏览器使用的推荐方案数据。

下游生成文件是 `data/unlocks.js`、`data/challenges.js`、`data/effects.js`、`data/effects-report.json`、`data/achievements.js` 和 `data/recommendation_profiles.js`。推荐配置源不会被改写。构建中途失败时，修复输入或依赖后重新运行完整命令，再进行发布。

**完整重建不包含缓存版本更新与离线版打包。** 成功后按第 5 节准备发布文件。

### 仅提供矩阵 HTML 的兼容模式

```bash
python tools/rebuild_data.py "temp/completion.html"
```

此模式复用已有 `tools/achievement_rewards_en.json`，保留已有 `data/achievements.js`，其余步骤照常执行。它不会重新解析全成就页，也不会纠正旧英文奖励映射。修复奖励映射或更新其他成就时，应使用上面的完整命令。

## 3. 数据来源与生成关系

`tools/` 中既有人工维护的配置，也有生成文件；不能只凭目录判断是否可手工修改。

| 输出 | 构建脚本 | 输入与依赖 |
|---|---|---|
| `tools/achievement_rewards_en.json` | `build_achievement_rewards_en.py` | 两份 HTML、EID 英文包 |
| `data/unlocks.js` | `build_unlocks.py` | 矩阵 HTML、英文奖励映射 |
| `data/challenges.js` | `build_challenges.py` | 矩阵 HTML、`tools/challenge_rewards.json` |
| `data/effects.js`、`data/effects-report.json` | `crawl_effects.py` | `data/unlocks.js`、EID 中英文包、`tools/non_eid_fallback_zh.json`、脚本内特殊规则 |
| `data/achievements.js` | `build_achievements.py` | 全成就 HTML、`tools/achievement_index.json`、EID 中文包 |
| `data/recommendation_profiles.js` | `build_recommendation_profiles.py` | `tools/recommendation_profiles.json` 及其引用的推荐配置 |
| `isaac-unlock-planner-offline.html` | `build_offline_html.py` | `index.html` 引用的样式、脚本、数据和图片 |

以上输出应通过脚本重建。可编辑的源配置包括挑战奖励元数据、成就分类索引、推荐方案及优先级、非 EID 中文兜底标签；展示层临时修正见第 4.6 节。

## 4. 按需维护与分步构建

只更新某一类数据时，可单独运行对应脚本。若更改了上游输入，需继续执行依赖它的下游构建；英文奖励映射变动后，应依次重建矩阵和中文效果。

### 4.1 英文奖励映射

```bash
python tools/build_achievement_rewards_en.py "temp/achievements.html" --completion-html "temp/completion.html"
```

生成器不读取旧映射或旧 `data/unlocks.js`，即使这些文件不存在，也能从输入构建。支持 `--output` 指定输出路径、`--refresh-eid` 刷新英文 EID 缓存。

生成规则：

1. 复用通关标记矩阵解析，确定需要的成就 ID 范围。
2. 复用 `build_achievements.py` 的全成就行解析及奖励链接提取，从**奖励列**读取 `C/T/K/P` 链接，去重并保留顺序。
3. 分别将链接解析为收藏品、饰品、卡牌、药丸的实体 ID，再查询 EID 英文名。语言包按 AB+、Repentance、Repentance+ 顺序合并；组合奖励用 ` / ` 连接。
4. 没有实体链接的奖励才使用成就英文标题。成就 175 的标题仅为 `O`，显式保留 `-0- Baby`；191 保留初始硬币说明；236/237 在实体名之前加 `Keeper holds`，保留初始携带语义。

成就标题不覆盖实际奖励实体。例如成就 113 的 `C179` 生成 `Fate`，183 的 `C361` 生成 `Fate's Reward`；成就 179 的实体名生成 `Farting Baby`，而非标题 `Fart Baby`。

缺少成就行、奖励实体在 EID 中不存在，或非实体奖励没有唯一英文标题时，构建报错，不沿用旧映射。

### 4.2 角色/Boss 矩阵与挑战

```bash
python tools/build_unlocks.py "temp/completion.html"
python tools/build_challenges.py "temp/completion.html"
```

矩阵构建器展开表格的跨行、跨列单元格，将同一角色共享成就 ID 的多个 Boss 合并为一条 `bossIds` 规则。奖励名取自英文奖励映射，默认 Boss 顺序以 Boss Rush 开头，其次为妈妈的心。

挑战构建器将 HTML 中的前置成就、奖励成就 ID 与 `tools/challenge_rewards.json` 合并。页面用前置成就判断挑战是否开放，用奖励成就判断挑战是否完成。矩阵和挑战数据均不保存优先级。

### 4.3 中文效果与匹配报告

```bash
python tools/crawl_effects.py
```

此脚本的刷新参数是 `--refresh`，与其他构建器的 `--refresh-eid` 不同。

构建器先处理脚本内明确指定的实体、组合奖励和初始携带说明。普通奖励使用以下匹配顺序：

1. 用 `data/unlocks.js` 的英文奖励名在 EID 英文包中定位实体。
2. 用相同的实体类型和 ID 取得 EID 中文名称与效果。
3. 英文匹配失败时，才尝试 `tools/non_eid_fallback_zh.json` 中的中文标签。
4. 仍无法匹配的角色、机制等奖励使用本地说明或通用兜底；Baby / 外观类可能保留“效果说明待补充”。

英文名称规范化只处理大小写、括号元数据和无关标点，不剥离罗马数字前缀；兼容别名用于处理旧名称或拼写差异。中文兜底不依赖推荐配置。

成就 227、228、233、542 使用组合奖励规则，191、236、237 使用店主初始能力说明。可在 `data/effects-report.json` 中检查各成就的匹配路径、实体 ID 和未匹配记录。

### 4.4 其他成就与描述修正

```bash
python tools/build_achievements.py "temp/achievements.html"
```

通过 `tools/achievement_index.json` 选择并组织主线、角色解锁、次数 / 累计、完成类成就。`cumulativeGroups` 保持相似累计链连续显示，`cumulativeSingles` 保存不分组的累计成就。

奖励列使用与英文映射相同的链接解析方法，再按实体 ID 获取 EID 中文名称和效果；存在实体链接但 EID 无法解析时直接报错。可用 `--refresh-eid` 刷新中文包。

成就 339 的保存页条件为空，构建器固定补充：

> 解锁除本成就以外的其他任意402个成就。

角色列表另插入默认角色“以撒”。其他成就的修正应放在输入配置或构建器中，避免下次重建覆盖手工编辑的输出。

### 4.5 推荐方案与优先级

| 配置 | 内容 |
|---|---|
| `tools/recommendation_profiles.json` | 方案列表、默认方案及引用文件 |
| `tools/recommendation_seed.json` | 角色/Boss 对的优先级 |
| `tools/challenge_priority.json` | 挑战 ID 的优先级 |

角色/Boss 配置条目只包含以下字段：

```json
{
  "characterId": "c00-isaac",
  "bossId": "satan",
  "priority": "strong"
}
```

挑战条目只包含 `challengeId` 和 `priority`。支持的优先级为 `strong`、`recommended`、`normal`、`discouraged`；未单独配置的角色/Boss 对默认使用 `normal`。

修改推荐源后运行：

```bash
python tools/validate_priorities.py
python tools/build_recommendation_profiles.py
```

校验器检查角色/Boss 对、捆绑解锁优先级的一致性和挑战配置完整性。新增方案时，在方案清单中指定角色/Boss 与挑战配置文件，再重新编译。

浏览器读取生成的 JS，不运行时请求配置 JSON。用户可在页面内调整优先级并导入、导出自己的配置；其他成就未设置推荐等级时使用 `normal`。推荐变动完成后，同样执行发布准备。

### 4.6 展示层临时覆盖

`data/overrides.js` 用成就 ID 覆盖名称、效果或图片，例如：

```js
window.ISAAC_OVERRIDES = {
  43: {
    effect: "你希望显示的自定义说明"
  }
};
```

支持 `name`、`effect`、`image`，不支持覆盖优先级。奖励实体映射错误应修复生成流程；这类展示覆盖不会修正上游映射或匹配报告。

## 5. 准备发布文件

数据或推荐配置构建完成后运行：

```bash
python tools/prepare_publish.py
```

该命令先更新 `index.html` 资源引用及 `styles.css` 精灵图引用中的缓存版本，再构建离线单文件。它只生成本地发布文件，不执行上传。

需要固定版本号时：

```bash
python tools/prepare_publish.py 20261003-1
```

只重新打包离线版、不更新缓存版本时：

```bash
python tools/build_offline_html.py
```

离线版内嵌样式、脚本、数据、图标及动态角色/Boss 图片，可脱离相邻资源打开。发布前检查普通页面与离线版中的奖励名称、效果和成就条件是否一致。

## 6. 数据规模与运行时约定

当前构建结果如下；更新输入后，以构建脚本输出和匹配报告为准。

| 项目 | 数量 |
|---|---:|
| 角色 | 34（17 表角色、17 堕化角色） |
| 通关标记 / Boss 目标 | 13 |
| 角色/Boss 解锁规则 | 340，其中 34 条为多 Boss 捆绑规则 |
| 挑战 | 45 |
| 其他成就列表条目 | 222 |
| 有效果或本地说明的通关奖励 | 308 / 340 |
| 未匹配的 Baby / 外观类奖励 | 32 |
| 其他成就中具有 EID 实体奖励的条目 | 112 |

页面默认按重要度排序，挑战可切回 ID 顺序。角色解锁列表不显示奖励列；主线成就图按存档进度区分解锁状态。成就图标使用本地 `Achievement_sprite.jpg`，按成就 ID 定位；角色头像来自 `assets/character/`。

存档解析独立于上述构建流程。`js/save-parser.js` 在浏览器本地校验 `ISAACNGSAVE09R  ` 魔数，读取 Achievement block，通过 `achievements[achievementId]` 判断解锁状态。工具不修改存档，也不进行 CRC 写回。
