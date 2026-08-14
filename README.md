# 以撒开荒解锁规划器

一个纯前端的《以撒的结合》开荒解锁规划器。浏览器直接读取 `persistentgamedata*.dat` 的成就块，根据角色/Boss 展示 Completion Mark 奖励，并用推荐优先级帮助新档决定先刷什么。

## 直接使用

1. 双击 `index.html`。
2. 点击 **读取 persistentgamedata**，或把 `.dat` 拖到顶部区域。
3. 在 **按角色 / 按 Boss** 两个页面之间切换。
4. 页面默认按 **重要度顺序** 排列；也可以切换回 **默认顺序**。
5. 载入存档后关闭 **显示已解锁**，即可只看还需要完成的目标。

存档解析全部发生在浏览器本地，不会上传。解析结构参考灰机 Wiki 的 `Persistentgamedata.js`，项目中重新实现为只读取 Achievement block 的最小解析器。

## 数据链

```text
Huiji Completion Mark 表 ───────> data/unlocks.js
                                   │
Bilibili 推荐清单 + 人工修订 ───> data/recommendations.js
                                   │
EID 中英文效果（构建阶段） ─────> data/effects.js
                                   │
本地人工修正 ───────────────────> data/overrides.js
                                   │
                                   ▼
                            js/app.js
                                   ▲
                                   │
                        js/save-parser.js
                                   ▲
                                   │
                       persistentgamedata.dat
```

数据层彼此独立，后续增加“按奖励”“路线规划”“只看强烈推荐”等页面时不需要改存档解析器。

## 当前数据规模

- 34 个角色（17 表 + 17 堕化）
- 13 个 Completion Mark / Boss 目标
- 340 条规范化解锁规则
- 其中 34 条是多 Boss 捆绑规则
- 推荐数据当前显式记录 187 条：
  - 61 条 `strong`（强烈推荐 / 红）
  - 120 条 `recommended`（推荐 / 黄）
  - 其他没有进入推荐表的规则默认也是 `normal`
- 推荐源中仍有 1 条没有进入当前 Boss 模型：游魂“完成所有困难模式 → 神性”，因为它是“全困难印记”元目标，不对应单个当前 Boss 行。
- EID 与本地机制兜底目前能为 **308 / 340** 条规则生成效果数据；剩余 32 条均为 Baby 类解锁。所有当前 `strong` / `recommended` 奖励均有非空效果说明。
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
  recommendations.js
  recommendations-report.json
  effects.js
  effects-report.json
  overrides.js
assets/
  character/
  boss/
  achievement/
    Achievement_sprite.jpg
tools/
  build_unlocks.py
  build_recommendations.py
  crawl_effects.py
  localize_assets.py
  recommendation_seed.json
  cache/eid/
```

## 更新数据

### 1. 重新从灰机 Wiki 保存页生成矩阵

把 `Project:存档/成就` 另存为 HTML 后运行：

```bash
python tools/build_unlocks.py "你的成就页面.html"
```

脚本会展开 `rowspan`，并把堕化角色共享同一 achievement ID 的多个 Boss 合并成一条 `bossIds[]` 规则。当前默认 Boss 顺序将 **Boss Rush 放在妈妈的心之前**。

### 2. 更新推荐清单

推荐来源记录为：

```text
https://www.bilibili.com/opus/1083165871339208713
```

结构化种子保存在：

```text
tools/recommendation_seed.json
```

v5 的新版升/降级修订固化在 `tools/build_recommendations.py` 的 `PRIORITY_OVERRIDES_BY_ACHIEVEMENT` 中。更新种子或修订后运行：

```bash
python tools/build_recommendations.py
```

网页运行时不会请求推荐来源；最终结果固定写入 `data/recommendations.js`。

### 3. 更新效果数据

```bash
python tools/crawl_effects.py --refresh
```

构建器会读取 External Item Descriptions：

1. 合并 AB+ → Repentance → Repentance+ 的简体中文收藏品、饰品、卡牌和胶囊描述；
2. 若中文名无法可靠匹配，则使用奖励英文名在 EID `en_us.lua` 中先定位实体类型与 ID；
3. 再用同一个 `category + entityId` 回查中文包，从而得到稳定的中文名称与效果。

例如旧版漏掉的 `Locust of Wrath` 会通过英文别名匹配到 EID 的 `Locust of War`（trinket ID 113），再得到中文“战争蝗虫”和对应说明。

**注意：**效果抓取器只在构建阶段联网；最终网页运行时不爬站点。

### 4. 人工修正

`data/overrides.js` 最后加载，优先级最高：

```js
window.ISAAC_OVERRIDES = {
  43: {
    priority: "strong",
    effect: "你希望显示的自定义说明"
  }
};
```

可覆盖 `priority`、`name`、`effect`、`image`。

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
- `tools/localize_assets.py` 不会覆盖用户提供的 13 张 Boss 图片，也不会覆盖 Achievement sprite；当前只负责角色头像等可选构建缓存。

## Windows 存档位置提示

页面顶部当前提示：

```text
%USERPROFILE%\Documents\My Games\Binding of Isaac Repentance
%USERPROFILE%\Documents\My Games\Binding of Isaac Repentance+\save_backups
```

在其中寻找时间最近的 `...persistentgamedata*.dat`；文件名中星号 `*` 对应的数字表示第几个存档。

## 当前展示约定

- 页面打开时默认按重要度排序。
- Boss 默认顺序以 Boss Rush 开头，其次为妈妈的心。
- 没有 EID 描述且不属于 Baby 的奖励，会显示统一说明：`解锁「XXX」这一非收藏道具 / 机制内容。`
- Baby 类解锁暂保留“效果说明待补充”。
- Achievement 图标来自本地 sprite，通过成就 ID 直接定位，不再依赖远程奖励图片。

## 数据来源

- 角色 × Boss × Achievement ID：用户提供的灰机 Wiki `Project:存档/成就` 保存页。
- 存档结构：用户提供的灰机 Wiki `Persistentgamedata.js`。
- 高价值推荐：狐九郎整理的 Bilibili 动态 `https://www.bilibili.com/opus/1083165871339208713`；其中 v 9.10 推荐数据来自 @UP主 陈哥1，最初版与 v 9.10 最新修订参考 @UP主 恺恺orz（`https://www.bilibili.com/video/BV11pj7zEEHL`），并叠加本项目用户提供的当前版本修订。
- 效果构建源：External Item Descriptions 的简体中文 / 英文数据。
- Boss 图片：用户提供的 13 张本地素材。
- Achievement 图标：用户提供的 20×33、64px 单格 sprite 图。

第三方数据仍归其各自作者/项目所有；如果准备公开发布此工具，请在发布前确认并遵守对应项目的数据使用与署名要求。
