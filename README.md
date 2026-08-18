# 以撒开荒解锁规划器

一个纯前端的《以撒的结合》开荒解锁规划器。浏览器直接读取 `persistentgamedata*.dat` 的成就块，根据角色、Boss 或挑战展示解锁奖励，并用推荐优先级帮助新档决定先刷什么。

[点击这里尝试](https://momo-tori.github.io/isaac_unlock_planner/)

## 直接使用

1. 通过 GitHub Pages、普通 FTP 静态空间、本地 HTTP 服务，或直接双击 `index.html` 打开页面。运行时不再 `fetch()` 推荐 JSON，推荐源会在发布前编译为普通 JS，因此传统静态服务器也可使用。
2. 点击 **读取 persistentgamedata**，或把 `.dat` 拖到顶部区域。
3. 在 **按角色 / 按 Boss / 挑战解锁 / 其他成就** 四个页面之间切换。
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
Huiji 全成就页 + achievement_index.json
                             ───> data/achievements.js
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
  （角色-Boss-priority，开发源）        （挑战-priority，开发源）
                              │       │
                              └── build_recommendation_profiles.py ──> data/recommendation_profiles.js
                                                                  │
                                                                  └── 即时排序/着色
                                   ▲
                                   │
                        js/save-parser.js
                                   ▲
                                   │
                       persistentgamedata.dat
```

`unlocks.js` / `challenges.js` 仍然不保存 priority。两个 JSON 是人工维护的推荐源，发布时只被编译进独立的 `data/recommendation_profiles.js`；游戏数据与推荐数据依然解耦。网页不会运行时请求 JSON。

## 当前数据规模

- 34 个角色（17 表 + 17 堕化）
- 13 个 Completion Mark / Boss 目标
- 45 个挑战解锁目标
- 201 条剩余成就列表：8 条主线、33 条角色解锁、83 条次数 / 累计型、77 条完成类
- 340 条规范化解锁规则
- 其中 34 条是多 Boss 捆绑规则
- 角色/Boss 推荐配置现在按 **角色-Boss 对** 记录在 `tools/recommendation_seed.json`；未记录的组合运行时默认 `normal`。当前按解锁规则折算后仍保持 61 条 `strong`、120 条 `recommended`，不会把 reward name 或 achievement ID 写进推荐配置。
- EID 与本地机制兜底目前能为 **307 / 340** 条规则生成效果数据；剩余 33 条均为 Baby / 外观类解锁。所有当前 `strong` / `recommended` 奖励均有非空效果说明。
- 挑战优先级：14 条 `strong`（强烈推荐）、13 条 `recommended`（推荐）、18 条 `normal`（普通）。
- 挑战页从灰机 Wiki 表读取挑战 ID、前置成就 ID、奖励成就 ID；奖励效果优先使用 EID，金心/金炸弹/充能钥匙和角色初始配置等机制型奖励使用本地说明。
- 其他成就页从灰机 Wiki 全成就页读取成就 ID、解锁条件、奖励与奖励链接，再按 `tools/achievement_index.json` 分成四类。角色解锁类只显示角色图标、解锁条件和解锁状态；其他类显示奖励名称与效果。
- 其他成就页目前 108 条成就带有可解析的 EID 实体奖励，覆盖收藏品、饰品、卡牌和药丸；奖励链接类型分别对应 `C` / `T` / `K` / `P`。
- EID 原始描述中的 `#` 分隔符按效果条目换行显示，避免长段文本挤在同一行。

## 目录

```text
index.html
isaac-unlock-planner-offline.html
styles.css
js/
  app.js
  save-parser.js
data/
  unlocks.js
  challenges.js
  achievements.js
  effects.js
  effects-report.json
  overrides.js
  recommendation_profiles.js
assets/
  icon.png
  character/
  boss/
  achievement/
    Achievement_sprite.jpg
tools/
  rebuild_data.py
  build_unlocks.py
  build_challenges.py
  build_achievements.py
  achievement_index.json
  build_offline_html.py
  validate_priorities.py
  build_recommendation_profiles.py
  bump_cache_version.py
  prepare_publish.py
  recommendation_profiles.json
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

该脚本会删除并重建 `data/unlocks.js`、`data/challenges.js`、`data/effects.js` 等**生成物**，运行 `validate_priorities.py` 检查优先级 JSON，再执行 `build_recommendation_profiles.py` 生成浏览器直接加载的 `data/recommendation_profiles.js`。优先级 JSON 本身是配置源，不会被 clean rebuild 改写。如果已经有最新 EID 构建缓存，可以省略 `--refresh-eid`。

`data/achievements.js` 当前由独立的全成就构建脚本生成，不在 `rebuild_data.py` 的旧矩阵重建链路里。

### 1. 重新从灰机 Wiki 保存页生成矩阵

把 `Project:存档/成就` 另存为 HTML 后运行：

```bash
python tools/build_unlocks.py "你的成就页面.html"
```

脚本会展开 `rowspan`，并把堕化角色共享同一 achievement ID 的多个 Boss 合并成一条 `bossIds[]` 规则。当前默认 Boss 顺序将 **Boss Rush 放在妈妈的心之前**。`achievementCatalog` 的奖励名来自 `tools/achievement_rewards_en.json`，只保存 canonical English name；构建器不会读取旧的 `data/unlocks.js`。

> 注意：`tools/achievement_rewards_en.json` 保存的是**实际解锁奖励的英文实体名**，不是 Achievement 标题。两者在少数情况下不同，例如 Achievement #179 的标题是 `Fart Baby`，但实际收藏品是 `Farting Baby`。

### 2. 重新从灰机 Wiki 保存页刷新挑战成就映射

同一份 `Project:存档/成就` HTML 还包含挑战表。运行：

```bash
python tools/build_challenges.py "你的成就页面.html"
```

脚本会把灰机页解析出的 `prerequisiteAchievementId` / `rewardAchievementId` 与 `tools/challenge_rewards.json` 中的奖励元数据合并，从零生成 45 条挑战数据。`data/challenges.js` **不包含 priority**。挑战页面通过前置成就 ID 判断挑战是否已经开放，通过奖励成就 ID 判断挑战是否已经完成。

### 3. 重新生成其他成就页数据

把灰机 Wiki 的全成就页另存为 HTML，并确认 `tools/achievement_index.json` 中维护了四类成就 ID 后运行：

```bash
python tools/build_achievements.py "temp/成就 - 以撒的结合中文维基 - 灰机wiki - 北京嘉闻杰诺网络科技有限公司.html"
```

脚本会从全成就页读取成就名称、解锁条件、奖励和奖励链接，再按 `tools/achievement_index.json` 分为主线成就、角色解锁类、次数 / 累计型成就、完成类成就。

`tools/achievement_index.json` 中的 `cumulativeGroups` 用于保持相似累计链在列表中连续显示，`cumulativeSingles` 则保存不需要分组的累计型成就。

奖励链接里的 `C` / `T` / `K` / `P` 分别映射到 EID 的收藏品、饰品、卡牌、药丸。构建器会用 `entityType + entityId` 从 EID 中文数据中取奖励名称和效果；如果链接指向的实体无法在 EID 中解析，脚本会直接失败，避免生成缺效果的奖励数据。需要强制刷新 EID 缓存时加 `--refresh-eid`。

角色解锁类会额外插入“以撒”默认行，图标使用 `assets/character/` 下的本地角色头像；主线成就顶部的 SVG 会按存档进度把未解锁节点显示为暗色。

### 4. 更新运行时优先级

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

不保存 `rewardName`、achievement ID，也不会写进 `unlocks.js`。`build_recommendation_profiles.py` 会把它与挑战优先级、成就优先级一起打包成独立的 `data/recommendation_profiles.js`，网页再即时决定排序、标签与红/黄/灰背景。

挑战优先级独立保存在：

```text
tools/challenge_priority.json
```

每条只保存 `challengeId + priority`。`data/challenges.js` 不保存优先级。

其他成就页优先级也保存在运行时推荐配置中，字段为 `achievements`；当前没有内置推荐等级时全部按 `normal` 初始化，用户可在每行最右侧菜单中修改。

修改这两个 JSON 后不需要重建游戏数据，只需发布前运行：

```bash
python tools/validate_priorities.py
python tools/build_recommendation_profiles.py
python tools/bump_cache_version.py
```

其中 `validate_priorities.py` 会检查角色/Boss 对是否真实存在、捆绑解锁的多个 Boss 是否保持同一优先级，以及挑战 ID 是否完整覆盖。

### 5. 更新效果数据

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

### 6. 发布前生成缓存版本和离线单文件

发布前推荐统一运行：

```bash
python tools/prepare_publish.py
```

该脚本会先调用 `tools/bump_cache_version.py` 更新 `index.html` 中 CSS、JS、数据脚本和图标的 cache-busting query string，再调用 `tools/build_offline_html.py` 生成 `isaac-unlock-planner-offline.html`。

也可以手动指定版本：

```bash
python tools/prepare_publish.py 20260818-1
```

如果只想重建离线单文件：

```bash
python tools/build_offline_html.py
```

离线构建器会把 `index.html` 引用的 CSS、JS、数据文件、`assets/icon.png`、CSS 内图片，以及运行时动态引用的角色 / Boss 图片内嵌进单个 HTML 文件。最终的 `isaac-unlock-planner-offline.html` 可以脱离网络和相邻资源直接打开。

### 7. 人工修正

`data/overrides.js` 最后加载，用于展示层人工修正：

```js
window.ISAAC_OVERRIDES = {
  43: {
    effect: "你希望显示的自定义说明"
  }
};
```

可覆盖 `name`、`effect`、`image`。**priority 不再允许从 overrides 覆盖**，唯一来源是运行时 JSON。

## 推荐方案、自定义与本地保存

- 首次打开时，如果浏览器没有用户推荐配置，会将 `data/recommendation_profiles.js` 中的默认方案复制到 `localStorage`。
- 切换内置推荐方案时，会把选中的方案复制为新的当前用户配置。
- 每条人物/Boss 成就最右侧都有 `⋮` 菜单，可即时改成 `strong / recommended / normal`；捆绑多个 Boss 的同一成就会同步修改全部对应 pair。
- 挑战页也有相同的 `⋮` 菜单，按 `challengeId` 保存修改。
- 其他成就页的主线、次数 / 累计型、完成类和角色解锁类同样有最右侧优先级菜单，按 achievement ID 保存修改。
- 当前配置可导出为 JSON，也可以重新导入。导入成功后会成为当前本地配置。
- 当前推荐配置只保存在当前站点 origin 的 `localStorage`；GitHub Pages 与另一个 FTP 域名之间不会共享浏览器数据。
- 成功读取的 `persistentgamedata` 原始内容也会保存在 `localStorage`，下次进入自动重新解析。浏览器不能在下次访问时静默读取原来的文件系统路径，因此游戏进度更新后仍需重新选择最新 `.dat`。页面提供“清除本地缓存”按钮。

内置多方案由 `tools/recommendation_profiles.json` 管理。以后添加新方案时，可以为它指定独立的角色/Boss JSON、挑战 JSON 与成就优先级数据，然后重新运行 `build_recommendation_profiles.py`。

## 存档解析

`js/save-parser.js` 只读取当前工具需要的 Achievement block：

- 校验 16 字节魔数 `ISAACNGSAVE09R  `
- 跳过 `0x10` 的 32-bit header word
- 要求第一个 block type 为 `1`
- 读取 `blockSize` / `achievementCount`
- 用 `achievements[achievementId]` 判断是否解锁

因此工具不会修改存档，也不需要 CRC 写回逻辑。

## 图片说明

- 网页图标使用 `assets/icon.png`。
- 34 个角色头像优先读取本地 `assets/character/<characterId>.png`。
- 13 个 Boss 选择图全部使用项目内的 `assets/boss/<bossId>.png`，来自用户提供的 Boss 图片包。
- 奖励和成就图片统一使用用户提供的 `assets/achievement/Achievement_sprite.jpg`。原图为 1280×2112，按 20 列 × 33 行切分，每格 64×64；Achievement ID 使用 `index = id - 1` 定位，因此无需运行时联网请求奖励图片。

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
- 其他成就页默认按重要度排序；角色解锁类没有“奖励”列，其余成就列表保留奖励名称与效果。
- 主线成就上方有横向 SVG 进度图；读取存档后，未解锁成就节点会显示为暗色。
- Boss 默认顺序以 Boss Rush 开头，其次为妈妈的心。
- 没有 EID 描述且不属于 Baby 的奖励，会显示统一说明：`解锁「XXX」这一非收藏道具 / 机制内容。`
- Baby 类解锁暂保留“效果说明待补充”。
- Achievement 图标来自本地 sprite，通过成就 ID 直接定位，不再依赖远程奖励图片。

## 数据来源

- 角色 × Boss × Achievement ID：用户提供的灰机 Wiki `Project:存档/成就` 保存页。
- 挑战 ID × 前置 Achievement ID × 奖励 Achievement ID：同一灰机 Wiki `Project:存档/成就` 保存页。
- 其他成就页的成就 ID、名称、解锁条件、奖励和奖励链接：用户提供的灰机 Wiki 全成就保存页；四类列表顺序来自 `tools/achievement_index.json`。
- 挑战奖励名称辅助核对：IsaacGuru Challenges；挑战奖励中文效果由 EID 提供，机制型奖励使用本地说明。
- 存档结构：用户提供的灰机 Wiki `Persistentgamedata.js`。
- 高价值推荐：狐九郎整理的 Bilibili 动态 `https://www.bilibili.com/opus/1083165871339208713`；其中 v 9.10 推荐数据来自 @UP主 陈哥1，最初版与 v 9.10 最新修订参考 @UP主 恺恺orz（`https://www.bilibili.com/video/BV11pj7zEEHL`），并叠加本项目用户提供的当前版本修订。
- 效果构建源：External Item Descriptions 的简体中文 / 英文数据。
- Boss 图片：用户提供的 13 张本地素材。
- 角色图片和网页图标：项目内 `assets/character/` 与 `assets/icon.png`。
- Achievement 图标：用户提供的 20×33、64px 单格 sprite 图。

第三方数据仍归其各自作者/项目所有；如果准备公开发布此工具，请在发布前确认并遵守对应项目的数据使用与署名要求。

## EID 名称匹配

主链路只使用英文名称：先在 EID `en_us` 数据中解析出 `category + entity ID`，再用相同 ID 从 `zh_cn` 数据中取得中文名称和效果。只有主链路完全失败后，才允许使用 `tools/non_eid_fallback_zh.json` 的独立中文标签走 `norm_zh_name()` 末级回退；该回退与推荐优先级完全解耦，也不会读取 `achievementCatalog` 的中文名，因为 catalog 已经是纯英文。

`norm_name()` 只保留英文匹配所需的最小规范化：转小写、移除方括号/圆括号元数据、移除空格与无关标点。不会再剥离罗马数字前缀，因此 `Cry Baby` 与 `Dry Baby` 分别规范化为 `crybaby` / `drybaby`。已知源数据中的英文拼写错误通过显式英文 alias 修正。

成就 `#227`、`#228`、`#233`、`#542` 属于一次解锁多个实体的特殊情况，构建器会生成 bundle 效果；店主的 `#191`、`#236`、`#237` 则使用人物初始携带物品的专门说明。
