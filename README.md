# 以撒开荒解锁规划器

一个纯前端的《以撒的结合》开荒解锁规划器。浏览器直接读取 `persistentgamedata*.dat` 的成就块，根据角色、Boss 或挑战展示解锁奖励，并用推荐优先级帮助新档决定先刷什么。

[点击这里尝试](https://momo-tori.github.io/isaac_unlock_planner/)

## 直接使用

1. 通过 GitHub Pages 或本地 HTTP 服务打开页面。因为优先级现在由浏览器运行时读取 JSON，直接双击 `index.html` 的 `file://` 模式可能被浏览器拦截 JSON 请求。

   本地调试可运行：

   ```bash
   python -m http.server 8000
   ```

   然后访问 `http://localhost:8000/`。
2. 点击 **读取 persistentgamedata**，或把 `.dat` 拖到顶部区域。
3. 在 **按角色 / 按 Boss / 挑战解锁** 三个页面之间切换。
4. 页面默认按 **重要度顺序** 排列；也可以切换回 **默认顺序**。
5. 载入存档后关闭 **显示已解锁**，即可只看还需要完成的目标。

存档解析全部发生在浏览器本地，不会上传。解析结构参考灰机 Wiki 的 `Persistentgamedata.js`，项目中重新实现为只读取 Achievement block 的最小解析器。

## 数据链

```text
Huiji Completion Mark 表 ───────> data/unlocks.js
                                   │
Huiji 挑战成就表 + challenge_rewards.json
                             ───> data/challenges.js
                                   │
EID 中英文效果（构建阶段） ─────> data/effects.js
                                   │
非 EID 中文末级兜底 ───────────> tools/non_eid_fallback_zh.json
                                   │
本地人工修正 ───────────────────> data/overrides.js
                                   │
                                   ▼
                            js/app.js
                              ▲       ▲
                              │       │
tools/recommendation_seed.json       tools/challenge_priority.json
  （角色-Boss-priority，运行时读取）   （挑战-priority，运行时读取）
                              │       │
                              └── fetch + 即时排序/着色 ──┘
                                   ▲
                                   │
                        js/save-parser.js
                                   ▲
                                   │
                       persistentgamedata.dat
```

**优先级不再写入任何 `data/*.js` 生成数据。** `unlocks.js` / `challenges.js` 只描述游戏数据；推荐配置由网页运行时直接读取两个 JSON。

## 当前数据规模

- 34 个角色（17 表 + 17 堕化）
- 13 个 Completion Mark / Boss 目标
- 45 个挑战解锁目标
- 340 条规范化解锁规则
- 其中 34 条是多 Boss 捆绑规则
- 角色/Boss 推荐配置现在按 **角色-Boss 对** 记录在 `tools/recommendation_seed.json`；未记录的组合运行时默认 `normal`。当前按解锁规则折算后仍保持 61 条 `strong`、120 条 `recommended`，不会把 reward name 或 achievement ID 写进推荐配置。
- EID 与本地机制兜底目前能为 **307 / 340** 条规则生成效果数据；剩余 33 条均为 Baby / 外观类解锁。所有当前 `strong` / `recommended` 奖励均有非空效果说明。
- 挑战优先级：14 条 `strong`（强烈推荐）、13 条 `recommended`（推荐）、18 条 `normal`（普通）。
- 挑战页从灰机 Wiki 表读取挑战 ID、前置成就 ID、奖励成就 ID；奖励效果优先使用 EID，金心/金炸弹/充能钥匙和角色初始配置等机制型奖励使用本地说明。
- EID 原始描述中的 `#` 分隔符按效果条目换行显示，避免长段文本挤在同一行。

## 目录

```text
index.html
styles.css
js/
  app.js
  save-parser.js
data/
  unlocks.js
  challenges.js
  effects.js
  effects-report.json
  overrides.js
assets/
  character/
  boss/
  achievement/
    Achievement_sprite.jpg
tools/
  rebuild_data.py
  build_unlocks.py
  build_challenges.py
  validate_priorities.py
  crawl_effects.py
  achievement_rewards_en.json
  challenge_rewards.json
  recommendation_seed.json
  challenge_priority.json
  non_eid_fallback_zh.json
  cache/eid/
```

## 更新数据

### 0. 从零重建全部生成数据

推荐使用统一入口：

```bash
python tools/rebuild_data.py "你的成就页面.html" --refresh-eid
```

该脚本会删除并重建 `data/unlocks.js`、`data/challenges.js`、`data/effects.js` 等**生成物**，然后运行 `validate_priorities.py` 检查两个运行时优先级 JSON。优先级 JSON 本身是配置源，不会被 clean rebuild 改写。如果已经有最新 EID 构建缓存，可以省略 `--refresh-eid`。

### 1. 重新从灰机 Wiki 保存页生成矩阵

把 `Project:存档/成就` 另存为 HTML 后运行：

```bash
python tools/build_unlocks.py "你的成就页面.html"
```

脚本会展开 `rowspan`，并把堕化角色共享同一 achievement ID 的多个 Boss 合并成一条 `bossIds[]` 规则。当前默认 Boss 顺序将 **Boss Rush 放在妈妈的心之前**。`achievementCatalog` 的奖励名来自 `tools/achievement_rewards_en.json`，只保存 canonical English name；构建器不会读取旧的 `data/unlocks.js`。

### 2. 重新从灰机 Wiki 保存页刷新挑战成就映射

同一份 `Project:存档/成就` HTML 还包含挑战表。运行：

```bash
python tools/build_challenges.py "你的成就页面.html"
```

脚本会把灰机页解析出的 `prerequisiteAchievementId` / `rewardAchievementId` 与 `tools/challenge_rewards.json` 中的奖励元数据合并，从零生成 45 条挑战数据。`data/challenges.js` **不包含 priority**。挑战页面通过前置成就 ID 判断挑战是否已经开放，通过奖励成就 ID 判断挑战是否已经完成。


### 3. 更新运行时优先级

人物/Boss 推荐来源记录在：

```text
tools/recommendation_seed.json
```

每条只包含：

```json
{
  "characterId": "c00-isaac",
  "bossId": "satan",
  "priority": "strong"
}
```

不保存 `rewardName`、achievement ID，也不会编译成 `data/recommendations.js`。网页启动时直接读取该 JSON，再用当前 `unlocks.js` 的角色/Boss 规则即时决定排序、标签与红/黄/灰背景。

挑战优先级独立保存在：

```text
tools/challenge_priority.json
```

每条只保存 `challengeId + priority`。`data/challenges.js` 不保存优先级。

修改这两个 JSON 后不需要重建数据，只需发布前运行：

```bash
python tools/validate_priorities.py
python tools/bump_cache_version.py
```

其中 `validate_priorities.py` 会检查角色/Boss 对是否真实存在、捆绑解锁的多个 Boss 是否保持同一优先级，以及挑战 ID 是否完整覆盖。

### 4. 更新效果数据

```bash
python tools/crawl_effects.py --refresh
```

构建器会读取 External Item Descriptions，并严格按以下顺序处理：

1. 使用 `unlocks.js` 中的 canonical English reward name 在 EID `en_us.lua` 中定位实体类型与 ID；
2. 用同一个 `category + entityId` 回查 `zh_cn.lua`，取得最终中文名称与效果；
3. 只有英文 EID 匹配失败时，才允许使用独立的 `tools/non_eid_fallback_zh.json` 中文名走一次旧中文匹配作为末级回退；
4. 仍然无法落到 EID 实体的角色、初始能力、掉落物/机制和 Baby 类，再进入本地特殊说明或通用机制兜底。

因此中文名称不会参与正常 EID 主匹配链路。

例如旧版漏掉的 `Locust of Wrath` 会通过英文别名匹配到 EID 的 `Locust of War`（trinket ID 113），再得到中文“战争蝗虫”和对应说明。

**注意：**效果抓取器只在构建阶段联网；最终网页运行时不爬站点。

### 5. 人工修正

`data/overrides.js` 最后加载，用于展示层人工修正：

```js
window.ISAAC_OVERRIDES = {
  43: {
    effect: "你希望显示的自定义说明"
  }
};
```

可覆盖 `name`、`effect`、`image`。**priority 不再允许从 overrides 覆盖**，唯一来源是运行时 JSON。

## 存档解析

`js/save-parser.js` 只读取当前工具需要的 Achievement block：

- 校验 16 字节魔数 `ISAACNGSAVE09R  `
- 跳过 `0x10` 的 32-bit header word
- 要求第一个 block type 为 `1`
- 读取 `blockSize` / `achievementCount`
- 用 `achievements[achievementId]` 判断是否解锁

因此工具不会修改存档，也不需要 CRC 写回逻辑。

## 图片说明

- 34 个角色头像优先读取本地 `assets/character/<characterId>.png`。
- 13 个 Boss 选择图全部使用项目内的 `assets/boss/<bossId>.png`，来自用户提供的 Boss 图片包。
- 奖励图片统一使用用户提供的 `assets/achievement/Achievement_sprite.jpg`。原图为 1280×2112，按 20 列 × 33 行切分，每格 64×64；Achievement ID 使用 `index = id - 1` 定位，因此无需运行时联网请求奖励图片。

## Windows 存档位置提示

页面顶部当前提示：

```text
%USERPROFILE%\Documents\My Games\Binding of Isaac Repentance
%USERPROFILE%\Documents\My Games\Binding of Isaac Repentance+\save_backups
```

在其中寻找时间最近的 `...persistentgamedata*.dat`；文件名中星号 `*` 对应的数字表示第几个存档。

## 当前展示约定

- 页面打开时默认按重要度排序。
- 挑战页默认同样按重要度排序；切换“默认顺序”后按挑战 ID 从小到大排列。
- Boss 默认顺序以 Boss Rush 开头，其次为妈妈的心。
- 没有 EID 描述且不属于 Baby 的奖励，会显示统一说明：`解锁「XXX」这一非收藏道具 / 机制内容。`
- Baby 类解锁暂保留“效果说明待补充”。
- Achievement 图标来自本地 sprite，通过成就 ID 直接定位，不再依赖远程奖励图片。

## 数据来源

- 角色 × Boss × Achievement ID：用户提供的灰机 Wiki `Project:存档/成就` 保存页。
- 挑战 ID × 前置 Achievement ID × 奖励 Achievement ID：同一灰机 Wiki `Project:存档/成就` 保存页。
- 挑战奖励名称辅助核对：IsaacGuru Challenges；挑战奖励中文效果由 EID 提供，机制型奖励使用本地说明。
- 存档结构：用户提供的灰机 Wiki `Persistentgamedata.js`。
- 高价值推荐：狐九郎整理的 Bilibili 动态 `https://www.bilibili.com/opus/1083165871339208713`；其中 v 9.10 推荐数据来自 @UP主 陈哥1，最初版与 v 9.10 最新修订参考 @UP主 恺恺orz（`https://www.bilibili.com/video/BV11pj7zEEHL`），并叠加本项目用户提供的当前版本修订。
- 效果构建源：External Item Descriptions 的简体中文 / 英文数据。
- Boss 图片：用户提供的 13 张本地素材。
- Achievement 图标：用户提供的 20×33、64px 单格 sprite 图。

第三方数据仍归其各自作者/项目所有；如果准备公开发布此工具，请在发布前确认并遵守对应项目的数据使用与署名要求。

## EID 名称匹配

主链路只使用英文名称：先在 EID `en_us` 数据中解析出 `category + entity ID`，再用相同 ID 从 `zh_cn` 数据中取得中文名称和效果。只有主链路完全失败后，才允许使用 `tools/non_eid_fallback_zh.json` 的独立中文标签走 `norm_zh_name()` 末级回退；该回退与推荐优先级完全解耦，也不会读取 `achievementCatalog` 的中文名，因为 catalog 已经是纯英文。

`norm_name()` 只保留英文匹配所需的最小规范化：转小写、移除方括号/圆括号元数据、移除空格与无关标点。不会再剥离罗马数字前缀，因此 `Cry Baby` 与 `Dry Baby` 分别规范化为 `crybaby` / `drybaby`。已知源数据中的英文拼写错误通过显式英文 alias 修正。

成就 `#227`、`#228`、`#233`、`#542` 属于一次解锁多个实体的特殊情况，构建器会生成 bundle 效果；店主的 `#191`、`#236`、`#237` 则使用人物初始携带物品的专门说明。
