(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.IsaacSaveParser = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  const MAGIC = 'ISAACNGSAVE09R  ';

  function asDataView(input) {
    if (input instanceof ArrayBuffer) return new DataView(input);
    if (ArrayBuffer.isView(input)) {
      return new DataView(input.buffer, input.byteOffset, input.byteLength);
    }
    throw new TypeError('parsePersistentGameData 需要 ArrayBuffer 或 TypedArray');
  }

  function parsePersistentGameData(input) {
    const dv = asDataView(input);
    if (dv.byteLength < 32) throw new Error('文件过短，不像 persistentgamedata 存档。');

    let cursor = 0;
    let magic = '';
    for (let i = 0; i < 16; i += 1) magic += String.fromCharCode(dv.getUint8(cursor++));
    if (magic !== MAGIC) {
      throw new Error(`存档格式不受支持：文件头为 ${JSON.stringify(magic)}`);
    }

    // 与灰机 Wiki Persistentgamedata.js 一致：0x10 读取一个 32-bit 字段，
    // 随后第一个 block 应为 achievements。
    const headerWord = dv.getUint32(cursor, true);
    cursor += 4;

    const blockType = dv.getUint32(cursor, true); cursor += 4;
    const blockSize = dv.getUint32(cursor, true); cursor += 4;
    const achievementCount = dv.getUint32(cursor, true); cursor += 4;

    if (blockType !== 1) throw new Error(`未找到成就块：第一个 block type = ${blockType}`);
    if (cursor + blockSize > dv.byteLength) throw new Error('成就块长度超过文件大小，存档可能损坏。');

    const achievements = [];
    for (let i = 0; i < blockSize; i += 1) {
      const value = dv.getUint8(cursor + i);
      if (i < achievementCount) achievements.push(value > 0);
    }

    let unlockedCount = 0;
    for (let i = 1; i < achievements.length; i += 1) if (achievements[i]) unlockedCount += 1;

    return {
      magic,
      headerWord,
      achievementBlockSize: blockSize,
      achievementCount,
      achievements,
      unlockedCount,
      isAchievementUnlocked(id) {
        return Number.isInteger(id) && id >= 0 && id < achievements.length && achievements[id] === true;
      }
    };
  }

  return { MAGIC, parsePersistentGameData };
});
