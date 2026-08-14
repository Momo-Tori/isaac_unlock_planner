# Third-party data attribution

This project combines several independently maintained data sources at build time.

- **Huiji Wiki / 以撒的结合中文维基**: character × completion-target × achievement-ID matrix, plus the challenge ID × prerequisite-achievement × reward-achievement table, supplied to this project as a saved HTML page by the user.
- **Bilibili unlock recommendation post**: 狐九郎整理的《【以撒的结合】v 9.10 更新版-萌新向人物道具解锁优先顺序（搬运整理）》：`https://www.bilibili.com/opus/1083165871339208713`. 其中 v 9.10 推荐数据来自 @UP主 陈哥1，最初版与 v 9.10 最新修订参考 @UP主 恺恺orz（`https://www.bilibili.com/video/BV11pj7zEEHL`）。本项目还叠加了用户在对话中提供的当前版本修订。
- **IsaacGuru Challenges**: used as an auxiliary English-name cross-check for challenge rewards (`https://isaacguru.com/challenges`).
- **External Item Descriptions (EID)**: Simplified-Chinese effect data used by the build-time effect generator. The effect builder also indexes the English EID packs first when a reward cannot be matched reliably by Chinese name, then resolves the same entity ID back to the Simplified-Chinese description.
- **IsaacGuru-hosted image URLs**: some pre-existing character/reward image metadata in `data/unlocks.js`; when both local and remote reward images fail, the app simply hides the image.
- **Boss artwork**: the 13 Boss selector images bundled in the project were supplied directly by the user.
- **Achievement sprite**: the 1280×2112 achievement sprite bundled in `assets/achievement/Achievement_sprite.jpg` was supplied directly by the user; the app treats it as a 20×33 grid of 64×64 cells and uses `achievementId - 1` as the sprite index.

The save parser was implemented from the `Persistentgamedata.js` file supplied by the user. Runtime save parsing is local-only.

Before redistributing or publishing a derived build, review the current upstream terms and attribution requirements for every third-party data/image source you include.

## Localized artwork builder

`tools/localize_assets.py` uses build-time artwork sources only; the parser/save data is not sent anywhere. Character portraits can be sourced from `saarsc/IsaacCasinoOBS`. The script deliberately does **not** fetch or overwrite Boss images or the Achievement sprite, because both are treated as curated user-provided project assets.
