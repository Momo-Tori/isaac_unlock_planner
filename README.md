# 以撒开荒解锁规划器

一个纯前端的《以撒的结合》开荒解锁规划器。浏览器直接读取 `persistentgamedata*.dat` 的成就块，根据角色、Boss、挑战和其他成就展示解锁奖励，并用推荐优先级帮助新档决定先刷什么。

[点击这里尝试](https://momo-tori.github.io/isaac_unlock_planner/)

## 主要功能

- 本地读取 `persistentgamedata*.dat`，不会上传存档。
- 按 **角色 / Boss / 挑战解锁 / 其他成就** 查看解锁进度。
- 默认按重要度排序，也可以切换回默认顺序。
- 支持隐藏已解锁目标，只保留还需要完成的内容。
- 支持在页面内调整推荐优先级，并导出 / 导入本地推荐配置。
- 提供离线单文件版本 `isaac-unlock-planner-offline.html`。

## 直接使用

1. 通过 GitHub Pages、普通 FTP 静态空间、本地 HTTP 服务，或直接双击 `index.html` 打开页面。
2. 点击 **读取 persistentgamedata**，或把 `.dat` 拖到顶部区域。
3. 在几个视图之间切换查看解锁目标。
4. 载入存档后关闭 **显示已解锁**，即可只看未完成目标。

页面顶部会提示常见 Windows 存档位置：

```text
%USERPROFILE%\Documents\My Games\Binding of Isaac Repentance
%USERPROFILE%\Documents\My Games\Binding of Isaac Repentance+\save_backups
```

在其中寻找时间最近的 `...persistentgamedata*.dat`；文件名中星号 `*` 对应第几个存档。

## 推荐配置

- 首次打开时，页面会把内置推荐方案复制到当前站点的 `localStorage`。
- 每条角色/Boss、挑战和其他成就记录右侧都有优先级菜单，可改成 `strong / recommended / normal`。
- 当前配置可导出为 JSON，也可以重新导入。
- 成功读取的存档原始内容也会保存在 `localStorage`，下次进入会自动重新解析。游戏进度更新后仍需重新选择最新 `.dat`。

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
  data-rebuild.md
  rebuild_data.py
  build_unlocks.py
  build_challenges.py
  build_achievements.py
  crawl_effects.py
  prepare_publish.py
```

## 开发与数据维护

数据生成、效果抓取、推荐配置校验、离线单文件构建等维护流程见 [tools/data-rebuild.md](tools/data-rebuild.md)。

存档解析由 `js/save-parser.js` 完成，只读取当前工具需要的 Achievement block。工具不会修改存档，也不需要 CRC 写回逻辑。

## 图片说明

- 网页图标使用 `assets/icon.png`。
- 角色头像读取本地 `assets/character/<characterId>.png`。
- Boss 选择图读取本地 `assets/boss/<bossId>.png`。
- 奖励和成就图片使用 `assets/achievement/Achievement_sprite.jpg`，按 Achievement ID 定位。

## 数据来源

- 角色、Boss、挑战和成就数据：灰机 Wiki 保存页。
- 挑战奖励名称辅助核对：IsaacGuru Challenges。
- 存档结构：灰机 Wiki `Persistentgamedata.js`。
- 高价值推荐：狐九郎整理的 Bilibili 动态，以及项目用户提供的当前版本修订。
- 效果构建源：External Item Descriptions 的简体中文 / 英文数据。
- Boss 图片：网络素材与自修改绘制图片。
- 角色图片、网页图标和 Achievement 图标：项目内素材。
