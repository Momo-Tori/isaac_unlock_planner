(function () {
  'use strict';

  const DATA = window.ISAAC_UNLOCK_DATA;
  const EFFECTS = window.ISAAC_EFFECTS?.entries || {};
  const CHALLENGES = window.ISAAC_CHALLENGE_DATA?.entries || [];
  const ACHIEVEMENTS = window.ISAAC_ACHIEVEMENT_DATA;
  const OVERRIDES = window.ISAAC_OVERRIDES || {};
  const PROFILE_BUNDLE = window.ISAAC_RECOMMENDATION_PROFILES;
  const Parser = window.IsaacSaveParser;

  const CACHE_VERSION = (() => {
    try {
      const src = document.currentScript && document.currentScript.src;
      return src ? (new URL(src, window.location.href).searchParams.get('v') || '') : '';
    } catch (_) {
      return '';
    }
  })();

  function versionedLocalUrl(url) {
    if (!url || !CACHE_VERSION || /^(?:https?:|data:|blob:)/i.test(url)) return url;
    const joiner = url.includes('?') ? '&' : '?';
    return `${url}${joiner}v=${encodeURIComponent(CACHE_VERSION)}`;
  }

  if (!DATA || !Parser || !PROFILE_BUNDLE || !ACHIEVEMENTS) {
    throw new Error('页面数据、推荐方案或存档解析器未加载。');
  }

  const PRIORITY_SCORE = { strong: 3, recommended: 2, normal: 1 };
  const PRIORITY_LABEL = { strong: '强烈推荐', recommended: '推荐', normal: '普通' };
  const PROFILE_FORMAT = 'isaac-unlock-planner-profile';
  const PROFILE_VERSION = 1;
  const STORAGE_KEYS = {
    profile: 'isaac_unlock_planner.current_profile.v1',
    save: 'isaac_unlock_planner.cached_save.v1',
    uiPreferences: 'isaac_unlock_planner.ui_preferences.v1'
  };
  const CLOUD_STORAGE_KEYS = {
    profile: 'isaac-unlock-planner-current-profile-v1',
    save: 'isaac-unlock-planner-cached-save-v1',
    uiPreferences: 'isaac-unlock-planner-ui-preferences-v1'
  };
  const CLOUD_CHUNK_SIZE = 900;
  const storageCache = new Map();
  const cloudMeta = new Map();
  let cloudStorageAvailable = false;

  const byId = (items) => new Map(items.map((x) => [x.id, x]));
  const characters = byId(DATA.characters);
  const bosses = byId(DATA.bosses);
  const rulesById = new Map(DATA.unlockRules.map((rule) => [rule.id, rule]));
  const validPairs = new Set(DATA.unlockRules.flatMap((rule) => rule.bossIds.map((bossId) => pairKey(rule.characterId, bossId))));
  const validChallengeIds = new Set(CHALLENGES.map((x) => Number(x.challengeId)));
  const achievementLists = [
    ACHIEVEMENTS.main,
    ACHIEVEMENTS.characters.normal,
    ACHIEVEMENTS.characters.tainted,
    ACHIEVEMENTS.cumulative,
    ACHIEVEMENTS.completion
  ];
  const validAchievementListIds = new Set(achievementLists.flat().map((x) => Number(x.achievementId)));
  const builtinProfiles = new Map((PROFILE_BUNDLE.profiles || []).map((x) => [x.id, x]));

  const runtimePriority = {
    recommendationByPair: new Map(),
    challengeById: new Map(),
    achievementById: new Map()
  };

  const state = {
    view: 'character',
    selectedCharacterId: DATA.characters[0].id,
    selectedBossId: DATA.bosses[0].id,
    sort: 'priority',
    showUnlocked: true,
    save: null,
    saveName: '',
    currentProfile: null,
    menuTarget: null,
    toastTimer: null,
    toastHideTimer: null
  };

  const el = {
    selectorSection: document.getElementById('selectorSection'),
    grid: document.getElementById('entityGrid'),
    selectorKicker: document.getElementById('selectorKicker'),
    selectorTitle: document.getElementById('selectorTitle'),
    selectionSummary: document.getElementById('selectionSummary'),
    tableHead: document.getElementById('tableHead'),
    tableBody: document.getElementById('tableBody'),
    standardResults: document.getElementById('standardResults'),
    achievementResults: document.getElementById('achievementResults'),
    showUnlocked: document.getElementById('showUnlocked'),
    saveInput: document.getElementById('saveInput'),
    loadSaveBtn: document.getElementById('loadSaveBtn'),
    clearSaveBtn: document.getElementById('clearSaveBtn'),
    saveStatus: document.getElementById('saveStatus'),
    dropZone: document.getElementById('dropZone'),
    profileSelect: document.getElementById('profileSelect'),
    profileStatus: document.getElementById('profileStatus'),
    importProfileBtn: document.getElementById('importProfileBtn'),
    exportProfileBtn: document.getElementById('exportProfileBtn'),
    profileImportInput: document.getElementById('profileImportInput'),
    priorityMenu: document.getElementById('priorityMenu'),
    toast: document.getElementById('toast')
  };

  function pairKey(characterId, bossId) {
    return `${characterId}::${bossId}`;
  }

  function normalizePriority(value) {
    return Object.prototype.hasOwnProperty.call(PRIORITY_SCORE, value) ? value : 'normal';
  }

  function storageBaseKey(key) {
    const entry = Object.entries(STORAGE_KEYS).find(([, value]) => value === key);
    return entry ? CLOUD_STORAGE_KEYS[entry[0]] : key.replace(/[^A-Za-z0-9_-]/g, '-');
  }

  function chunkKey(base, index) {
    return `${base}-${index}`;
  }

  function splitCloudChunks(value) {
    const encoder = new TextEncoder();
    const chunks = [];
    let current = '';
    let currentBytes = 0;
    for (const char of String(value)) {
      const charBytes = encoder.encode(char).length;
      if (current && currentBytes + charBytes > CLOUD_CHUNK_SIZE) {
        chunks.push(current);
        current = '';
        currentBytes = 0;
      }
      current += char;
      currentBytes += charBytes;
    }
    chunks.push(current);
    return chunks;
  }

  function assembleCloudValue(base, raw) {
    const metaText = raw[base];
    if (!metaText) return null;
    const meta = JSON.parse(metaText);
    if (Number(meta.version) !== 1 || !Number.isInteger(meta.chunks) || meta.chunks < 0) throw new Error(`云缓存 ${base} 格式不受支持`);
    let value = '';
    for (let i = 0; i < meta.chunks; i++) {
      const part = raw[chunkKey(base, i)];
      if (typeof part !== 'string') throw new Error(`云缓存 ${base} 分片缺失`);
      value += part;
    }
    cloudMeta.set(base, meta);
    return value;
  }

  async function initStorage() {
    const toy = window.toy;
    const canUseCloud = Boolean(toy?.getCloudStorage && toy?.setCloudStorage && toy?.removeCloudStorage);
    if (canUseCloud) {
      try {
        const supported = toy.isSupport
          ? await Promise.all(['getCloudStorage', 'setCloudStorage', 'removeCloudStorage'].map((ability) => toy.isSupport(ability)))
          : [true, true, true];
        cloudStorageAvailable = supported.every(Boolean);
      } catch (error) {
        console.warn('Toy CloudStorage 支持检测失败，将使用浏览器本地缓存。', error);
        cloudStorageAvailable = false;
      }
    }

    if (cloudStorageAvailable) {
      try {
        const raw = await toy.getCloudStorage();
        for (const key of Object.values(STORAGE_KEYS)) {
          const base = storageBaseKey(key);
          const value = assembleCloudValue(base, raw);
          if (value !== null) storageCache.set(key, value);
        }
      } catch (error) {
        console.warn('Toy CloudStorage 读取失败，将使用浏览器本地缓存。', error);
        cloudStorageAvailable = false;
      }
    }

    for (const key of Object.values(STORAGE_KEYS)) {
      if (storageCache.has(key)) continue;
      const localValue = localStorageGet(key);
      if (localValue !== null) {
        storageCache.set(key, localValue);
        if (cloudStorageAvailable) persistStorageValue(key, localValue);
      }
    }
  }

  function localStorageGet(key) {
    try { return window.localStorage.getItem(key); }
    catch (error) { console.warn('localStorage 读取失败：', error); return null; }
  }

  function localStorageSet(key, value) {
    try { window.localStorage.setItem(key, value); return true; }
    catch (error) { console.warn('localStorage 写入失败：', error); return false; }
  }

  function localStorageRemove(key) {
    try { window.localStorage.removeItem(key); }
    catch (error) { console.warn('localStorage 删除失败：', error); }
  }

  function safeStorageGet(key) {
    return storageCache.has(key) ? storageCache.get(key) : null;
  }

  function safeStorageSet(key, value) {
    storageCache.set(key, value);
    persistStorageValue(key, value);
    return true;
  }

  function showToast(message) {
    if (!el.toast) return;
    window.clearTimeout(state.toastTimer);
    window.clearTimeout(state.toastHideTimer);
    el.toast.textContent = message;
    el.toast.hidden = false;
    requestAnimationFrame(() => el.toast.classList.add('show'));
    state.toastTimer = window.setTimeout(() => {
      el.toast.classList.remove('show');
      state.toastHideTimer = window.setTimeout(() => { el.toast.hidden = true; }, 180);
    }, 1800);
  }

  async function copyTextCompat(text) {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (error) {
      console.warn('Async Clipboard unavailable:', error);
    }

    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    textarea.style.pointerEvents = 'none';
    textarea.style.top = '0';
    textarea.style.left = '0';
    document.body.appendChild(textarea);

    textarea.focus();
    textarea.select();
    textarea.setSelectionRange(0, text.length);

    let success = false;
    try {
      success = document.execCommand('copy');
    } catch (error) {
      console.warn('Fallback copy unavailable:', error);
    }

    textarea.remove();
    return success;
  }

  function showManualCopyDialog(text) {
    let dialog = document.getElementById('manualCopyDialog');
    if (!dialog) {
      dialog = document.createElement('div');
      dialog.id = 'manualCopyDialog';
      dialog.className = 'manual-copy-backdrop';
      dialog.innerHTML = `
        <div class="manual-copy-dialog" role="dialog" aria-modal="true" aria-labelledby="manualCopyTitle">
          <div class="manual-copy-heading">
            <strong id="manualCopyTitle">当前平台限制了自动复制</strong>
            <button type="button" class="manual-copy-close" aria-label="关闭">×</button>
          </div>
          <p>请手动复制下面的路径，然后按 Ctrl+C。</p>
          <input class="manual-copy-input" type="text" readonly />
        </div>
      `;
      document.body.appendChild(dialog);
      dialog.addEventListener('click', (event) => {
        if (event.target === dialog || event.target.closest('.manual-copy-close')) dialog.hidden = true;
      });
      dialog.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') dialog.hidden = true;
      });
    }

    const input = dialog.querySelector('.manual-copy-input');
    input.value = text;
    dialog.hidden = false;
    requestAnimationFrame(() => {
      input.focus();
      input.select();
      input.setSelectionRange(0, text.length);
    });
  }

  function safeStorageRemove(key) {
    storageCache.delete(key);
    removeStorageValue(key);
  }

  async function persistStorageValue(key, value) {
    localStorageSet(key, value);
    if (!cloudStorageAvailable) return;
    const base = storageBaseKey(key);
    const chunks = splitCloudChunks(value);
    if (chunks.length > 120) {
      console.warn(`缓存 ${base} 超出 Toy CloudStorage 建议分片数量，已保留浏览器本地缓存。`);
      showToast('缓存过大，已暂存到本地');
      return;
    }
    const items = {
      [base]: JSON.stringify({ version: 1, chunks: chunks.length, updatedAt: new Date().toISOString() })
    };
    chunks.forEach((part, index) => { items[chunkKey(base, index)] = part; });
    try {
      await window.toy.setCloudStorage(items);
      const previous = cloudMeta.get(base);
      if (previous?.chunks > chunks.length) {
        const staleKeys = [];
        for (let i = chunks.length; i < previous.chunks; i++) staleKeys.push(chunkKey(base, i));
        await window.toy.removeCloudStorage(staleKeys);
      }
      cloudMeta.set(base, { version: 1, chunks: chunks.length });
    } catch (error) {
      console.warn('Toy CloudStorage 写入失败，已保留浏览器本地缓存。', error);
      showToast('云端缓存写入失败，已暂存到本地');
    }
  }

  async function removeStorageValue(key) {
    localStorageRemove(key);
    if (!cloudStorageAvailable) return;
    const base = storageBaseKey(key);
    const previous = cloudMeta.get(base);
    const keys = [base];
    for (let i = 0; i < (previous?.chunks || 0); i++) keys.push(chunkKey(base, i));
    try {
      await window.toy.removeCloudStorage(keys);
      cloudMeta.delete(base);
    } catch (error) {
      console.warn('Toy CloudStorage 删除失败。', error);
      showToast('云端缓存删除失败');
    }
  }

  function persistUiPreferences() {
    safeStorageSet(STORAGE_KEYS.uiPreferences, JSON.stringify({
      version: 1,
      sort: state.sort,
      showUnlocked: state.showUnlocked
    }));
  }

  function restoreUiPreferences() {
    const stored = safeStorageGet(STORAGE_KEYS.uiPreferences);
    if (!stored) return;
    try {
      const payload = JSON.parse(stored);
      if (Number(payload.version) !== 1) throw new Error('偏好格式不受支持');
      if (payload.sort === 'default' || payload.sort === 'priority') state.sort = payload.sort;
      if (typeof payload.showUnlocked === 'boolean') state.showUnlocked = payload.showUnlocked;
    } catch (error) {
      console.warn('本地页面偏好损坏，已清除。', error);
      safeStorageRemove(STORAGE_KEYS.uiPreferences);
    }
  }

  function esc(value) {
    return String(value ?? '').replace(/[&<>'"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
  }

  function imageUrlList(values) {
    return values.flat().filter(Boolean);
  }

  function safeImage(urls, className) {
    const sources = imageUrlList(Array.isArray(urls) ? urls : [urls]);
    if (!sources.length) return '';
    const first = sources[0];
    const rest = sources.slice(1).join('|');
    return `<img class="${className}" src="${esc(first)}" alt="" aria-hidden="true" loading="lazy" data-next-sources="${esc(rest)}" onerror="const q=this.dataset.nextSources?this.dataset.nextSources.split('|').filter(Boolean):[];if(q.length){this.src=q.shift();this.dataset.nextSources=q.join('|')}else{this.remove()}" />`;
  }

  function characterLocalImage(character) {
    return versionedLocalUrl(`./assets/character/${character.id}.png`);
  }

  function bossImage(boss) {
    return [versionedLocalUrl(`./assets/boss/${boss.id}.png`)];
  }

  const ACHIEVEMENT_SPRITE = { columns: 20, rows: 33, cell: 64, maxId: 660 };

  function achievementSprite(aid) {
    const id = Number(aid);
    if (!Number.isInteger(id) || id < 1 || id > ACHIEVEMENT_SPRITE.maxId) return '';
    const index = id - 1;
    const col = index % ACHIEVEMENT_SPRITE.columns;
    const row = Math.floor(index / ACHIEVEMENT_SPRITE.columns);
    return `<span class="achievement-sprite" aria-hidden="true" style="--ach-x:${-col * ACHIEVEMENT_SPRITE.cell}px;--ach-y:${-row * ACHIEVEMENT_SPRITE.cell}px"></span>`;
  }

  function isBabyReward(name) {
    const text = String(name || '');
    return /baby/i.test(text) || text.includes('宝宝');
  }

  function rewardFor(aid) {
    const key = String(aid);
    const base = DATA.achievementCatalog[key] || { name: `成就 #${aid}`, condition: '', image: null, effect: '' };
    const effectData = EFFECTS[key] || {};
    const override = OVERRIDES[key] || OVERRIDES[aid] || {};
    const merged = { ...base, ...effectData, ...override };
    return {
      ...merged,
      name: merged.name || `成就 #${aid}`,
      image: merged.image || base.image || null,
      effect: merged.effect || '',
      condition: base.condition || merged.condition || ''
    };
  }

  function rulePriority(rule) {
    let best = 'normal';
    for (const bossId of rule.bossIds) {
      const priority = runtimePriority.recommendationByPair.get(pairKey(rule.characterId, bossId)) || 'normal';
      if (PRIORITY_SCORE[priority] > PRIORITY_SCORE[best]) best = priority;
    }
    return best;
  }

  function challengePriority(challengeId) {
    return runtimePriority.challengeById.get(Number(challengeId)) || 'normal';
  }

  function achievementPriority(achievementId) {
    return runtimePriority.achievementById.get(Number(achievementId)) || 'normal';
  }

  function unlockStatus(aid) {
    if (!state.save) return null;
    return state.save.isAchievementUnlocked(aid);
  }

  function statusBadge(unlocked) {
    if (unlocked === true) return '<span class="status-badge unlocked">已解锁</span>';
    if (unlocked === false) return '<span class="status-badge locked">未解锁</span>';
    return '<span class="status-badge unknown">未载入存档</span>';
  }

  function priorityPill(priority) {
    return `<span class="priority-pill">${PRIORITY_LABEL[priority]}</span>`;
  }

  function requirementText(rule, currentBossId) {
    if (rule.bossIds.length <= 1) return '';
    const names = rule.bossIds.map((id) => bosses.get(id)?.name || id);
    const prefix = currentBossId ? '同一奖励需要全部完成' : '捆绑解锁';
    return `<div class="requirement">${prefix}：${esc(names.join(' + '))}</div>`;
  }

  // ---------- Recommendation profile persistence ----------

  function snapshotFromBuiltin(profile) {
    return {
      format: PROFILE_FORMAT,
      version: PROFILE_VERSION,
      name: profile.name || profile.id,
      description: profile.description || '',
      source: profile.source || '',
      baseProfileId: profile.id,
      customized: false,
      updatedAt: new Date().toISOString(),
      characterBoss: (profile.characterBoss || []).map((x) => ({
        characterId: x.characterId,
        bossId: x.bossId,
        priority: normalizePriority(x.priority)
      })),
      challenges: (profile.challenges || []).map((x) => ({
        challengeId: Number(x.challengeId),
        priority: normalizePriority(x.priority)
      })),
      achievements: []
    };
  }

  function validateProfileSnapshot(raw) {
    if (!raw || typeof raw !== 'object') throw new Error('配置文件不是有效对象。');
    if (raw.format !== PROFILE_FORMAT) throw new Error(`配置格式不受支持，应为 ${PROFILE_FORMAT}。`);
    if (Number(raw.version) !== PROFILE_VERSION) throw new Error(`配置版本不受支持：${raw.version}`);
    if (!Array.isArray(raw.characterBoss) || !Array.isArray(raw.challenges)) throw new Error('配置缺少 characterBoss / challenges 数组。');

    const pairMap = new Map();
    for (const entry of raw.characterBoss) {
      if (!entry || !characters.has(entry.characterId) || !bosses.has(entry.bossId)) {
        throw new Error(`配置包含未知角色/Boss：${entry?.characterId || '?'} / ${entry?.bossId || '?'}`);
      }
      const key = pairKey(entry.characterId, entry.bossId);
      if (!validPairs.has(key)) throw new Error(`该角色/Boss 不存在解锁规则：${entry.characterId} / ${entry.bossId}`);
      if (pairMap.has(key)) throw new Error(`配置包含重复角色/Boss：${entry.characterId} / ${entry.bossId}`);
      const priority = normalizePriority(entry.priority);
      if (priority !== entry.priority) throw new Error(`无效优先级：${entry.priority}`);
      if (priority !== 'normal') pairMap.set(key, priority);
    }

    // Bundled tainted rewards must stay consistent across every Boss contained in the same achievement rule.
    for (const rule of DATA.unlockRules) {
      if (rule.bossIds.length <= 1) continue;
      const values = rule.bossIds.map((bossId) => pairMap.get(pairKey(rule.characterId, bossId)) || 'normal');
      if (new Set(values).size !== 1) {
        throw new Error(`捆绑成就 #${rule.achievementId} 的多个 Boss 优先级不一致。`);
      }
    }

    const challengeMap = new Map();
    for (const entry of raw.challenges) {
      const cid = Number(entry?.challengeId);
      if (!validChallengeIds.has(cid)) throw new Error(`配置包含未知挑战 ID：${entry?.challengeId}`);
      if (challengeMap.has(cid)) throw new Error(`配置包含重复挑战 ID：${cid}`);
      const priority = normalizePriority(entry.priority);
      if (priority !== entry.priority) throw new Error(`无效挑战优先级：${entry.priority}`);
      if (priority !== 'normal') challengeMap.set(cid, priority);
    }

    const achievementMap = new Map();
    for (const entry of raw.achievements || []) {
      const aid = Number(entry?.achievementId);
      if (!validAchievementListIds.has(aid)) throw new Error(`配置包含未知成就 ID：${entry?.achievementId}`);
      if (achievementMap.has(aid)) throw new Error(`配置包含重复成就 ID：${aid}`);
      const priority = normalizePriority(entry.priority);
      if (priority !== entry.priority) throw new Error(`无效成就优先级：${entry.priority}`);
      if (priority !== 'normal') achievementMap.set(aid, priority);
    }

    return {
      format: PROFILE_FORMAT,
      version: PROFILE_VERSION,
      name: String(raw.name || '自定义推荐'),
      description: String(raw.description || ''),
      source: String(raw.source || ''),
      baseProfileId: builtinProfiles.has(raw.baseProfileId) ? raw.baseProfileId : null,
      customized: Boolean(raw.customized),
      updatedAt: String(raw.updatedAt || new Date().toISOString()),
      pairMap,
      challengeMap,
      achievementMap
    };
  }

  function currentProfilePayload() {
    const characterBoss = [...runtimePriority.recommendationByPair.entries()]
      .map(([key, priority]) => {
        const [characterId, bossId] = key.split('::');
        return { characterId, bossId, priority };
      })
      .sort((a, b) => {
        const ca = characters.get(a.characterId)?.order ?? 999;
        const cb = characters.get(b.characterId)?.order ?? 999;
        const ba = bosses.get(a.bossId)?.order ?? 999;
        const bb = bosses.get(b.bossId)?.order ?? 999;
        return ca - cb || ba - bb || a.bossId.localeCompare(b.bossId);
      });

    const challenges = CHALLENGES.map((challenge) => ({
      challengeId: Number(challenge.challengeId),
      priority: challengePriority(challenge.challengeId)
    }));

    const achievements = [...validAchievementListIds].sort((a, b) => a - b).map((achievementId) => ({
      achievementId,
      priority: achievementPriority(achievementId)
    }));

    return {
      format: PROFILE_FORMAT,
      version: PROFILE_VERSION,
      name: state.currentProfile?.name || '自定义推荐',
      description: state.currentProfile?.description || '',
      source: state.currentProfile?.source || '',
      baseProfileId: state.currentProfile?.baseProfileId || null,
      customized: Boolean(state.currentProfile?.customized),
      updatedAt: new Date().toISOString(),
      characterBoss,
      challenges,
      achievements
    };
  }

  function persistCurrentProfile() {
    if (!state.currentProfile) return;
    const payload = currentProfilePayload();
    state.currentProfile.updatedAt = payload.updatedAt;
    safeStorageSet(STORAGE_KEYS.profile, JSON.stringify(payload));
  }

  function applyProfileSnapshot(raw, { persist = true } = {}) {
    const parsed = validateProfileSnapshot(raw);
    runtimePriority.recommendationByPair = parsed.pairMap;
    runtimePriority.challengeById = parsed.challengeMap;
    runtimePriority.achievementById = parsed.achievementMap;
    state.currentProfile = {
      format: parsed.format,
      version: parsed.version,
      name: parsed.name,
      description: parsed.description,
      source: parsed.source,
      baseProfileId: parsed.baseProfileId,
      customized: parsed.customized,
      updatedAt: parsed.updatedAt
    };
    if (persist) persistCurrentProfile();
  }

  function initializeRecommendationProfile() {
    const stored = safeStorageGet(STORAGE_KEYS.profile);
    if (stored) {
      try {
        applyProfileSnapshot(JSON.parse(stored), { persist: false });
        return;
      } catch (error) {
        console.warn('已保存的推荐配置无效，将恢复默认方案。', error);
        safeStorageRemove(STORAGE_KEYS.profile);
      }
    }

    const defaultProfile = builtinProfiles.get(PROFILE_BUNDLE.defaultProfileId) || PROFILE_BUNDLE.profiles?.[0];
    if (!defaultProfile) throw new Error('没有可用的内置推荐方案。');
    applyProfileSnapshot(snapshotFromBuiltin(defaultProfile), { persist: true });
  }

  function markProfileCustomized() {
    if (!state.currentProfile) return;
    state.currentProfile.customized = true;
    persistCurrentProfile();
  }

  function setRulePriority(ruleId, priority) {
    const rule = rulesById.get(ruleId);
    if (!rule) return;
    const normalized = normalizePriority(priority);
    for (const bossId of rule.bossIds) {
      const key = pairKey(rule.characterId, bossId);
      if (normalized === 'normal') runtimePriority.recommendationByPair.delete(key);
      else runtimePriority.recommendationByPair.set(key, normalized);
    }
    markProfileCustomized();
    closePriorityMenu();
    render();
  }

  function setChallengePriority(challengeId, priority) {
    const cid = Number(challengeId);
    if (!validChallengeIds.has(cid)) return;
    const normalized = normalizePriority(priority);
    if (normalized === 'normal') runtimePriority.challengeById.delete(cid);
    else runtimePriority.challengeById.set(cid, normalized);
    markProfileCustomized();
    closePriorityMenu();
    render();
  }

  function setAchievementPriority(achievementId, priority) {
    const aid = Number(achievementId);
    if (!validAchievementListIds.has(aid)) return;
    const normalized = normalizePriority(priority);
    if (normalized === 'normal') runtimePriority.achievementById.delete(aid);
    else runtimePriority.achievementById.set(aid, normalized);
    markProfileCustomized();
    closePriorityMenu();
    render();
  }

  function renderProfileControls() {
    const current = state.currentProfile;
    if (!current) return;
    const options = [];
    const isExactBuiltin = !current.customized && current.baseProfileId && builtinProfiles.has(current.baseProfileId);
    if (!isExactBuiltin) {
      options.push(`<option value="__current__">当前：${esc(current.name)}${current.customized ? '（已自定义）' : ''}</option>`);
    }
    for (const profile of PROFILE_BUNDLE.profiles || []) {
      options.push(`<option value="${esc(profile.id)}">${esc(profile.name)}</option>`);
    }
    el.profileSelect.innerHTML = options.join('');
    el.profileSelect.value = isExactBuiltin ? current.baseProfileId : '__current__';
    el.profileStatus.textContent = current.customized ? '修改已保存' : '当前方案已保存';
  }

  function switchBuiltinProfile(profileId) {
    const profile = builtinProfiles.get(profileId);
    if (!profile) return;
    if (state.currentProfile?.customized) {
      const ok = window.confirm('切换推荐方案会覆盖当前自定义修改。建议先导出配置。是否继续？');
      if (!ok) { renderProfileControls(); return; }
    }
    applyProfileSnapshot(snapshotFromBuiltin(profile), { persist: true });
    render();
  }

  function sanitizeFileName(name) {
    return String(name || 'recommendation-profile').replace(/[\\/:*?"<>|]+/g, '_').trim() || 'recommendation-profile';
  }

  function exportCurrentProfile() {
    const payload = currentProfilePayload();
    payload.exportedAt = new Date().toISOString();
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${sanitizeFileName(payload.name)}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function importProfileFile(file) {
    if (!file) return;
    try {
      const raw = JSON.parse(await file.text());
      raw.customized = true;
      raw.name = raw.name || file.name.replace(/\.json$/i, '');
      applyProfileSnapshot(raw, { persist: true });
      el.profileStatus.textContent = `已导入 ${file.name}`;
      render();
    } catch (error) {
      window.alert(`导入配置失败：${error?.message || String(error)}`);
    } finally {
      el.profileImportInput.value = '';
    }
  }

  // ---------- Save persistence ----------

  function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode(...bytes.subarray(i, Math.min(i + chunk, bytes.length)));
    }
    return btoa(binary);
  }

  function base64ToArrayBuffer(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return bytes.buffer;
  }

  function setSaveStatus(type, title, detail) {
    el.saveStatus.innerHTML = `<span class="status-dot ${type}"></span><div><strong title="${esc(title)}">${esc(title)}</strong><small>${esc(detail)}</small></div>`;
    el.clearSaveBtn.hidden = !state.save && !safeStorageGet(STORAGE_KEYS.save);
  }

  function applySaveBuffer(buffer, name, { restored = false, persist = false, lastModified = 0 } = {}) {
    const parsed = Parser.parsePersistentGameData(buffer);
    state.save = parsed;
    state.saveName = name || 'persistentgamedata.dat';
    if (persist) {
      safeStorageSet(STORAGE_KEYS.save, JSON.stringify({
        version: 1,
        name: state.saveName,
        lastModified: Number(lastModified || 0),
        storedAt: new Date().toISOString(),
        data: arrayBufferToBase64(buffer)
      }));
    }
    const prefix = restored ? '已从缓存恢复 · ' : '';
    setSaveStatus('ready', state.saveName, `${prefix}已解锁 ${parsed.unlockedCount} 个成就 · 成就块 ${parsed.achievementCount} 项`);
  }

  async function loadSave(file) {
    if (!file) return;
    try {
      const buffer = await file.arrayBuffer();
      applySaveBuffer(buffer, file.name, { persist: true, lastModified: file.lastModified });
      render();
    } catch (error) {
      setSaveStatus('error', '读取失败', error?.message || String(error));
    }
  }

  function restorePersistedSave() {
    const stored = safeStorageGet(STORAGE_KEYS.save);
    if (!stored) return;
    try {
      const payload = JSON.parse(stored);
      if (Number(payload.version) !== 1 || !payload.data) throw new Error('缓存格式不受支持');
      applySaveBuffer(base64ToArrayBuffer(payload.data), payload.name, { restored: true, persist: false, lastModified: payload.lastModified });
    } catch (error) {
      console.warn('存档缓存损坏，已清除。', error);
      safeStorageRemove(STORAGE_KEYS.save);
      state.save = null;
      state.saveName = '';
      setSaveStatus('error', '存档缓存已失效', '请重新读取最新 persistentgamedata。');
    }
  }

  function clearPersistedSave() {
    safeStorageRemove(STORAGE_KEYS.save);
    state.save = null;
    state.saveName = '';
    el.saveInput.value = '';
    setSaveStatus('idle', '尚未读取存档', '文件只在当前页面解析，不会上传到本工具服务器。');
    render();
  }

  // ---------- UI rendering ----------

  function ruleRows() {
    let rules;
    if (state.view === 'character') {
      rules = DATA.unlockRules.filter((r) => r.characterId === state.selectedCharacterId);
    } else {
      rules = DATA.unlockRules.filter((r) => r.bossIds.includes(state.selectedBossId));
    }

    const decorated = rules.map((rule) => ({
      rule,
      reward: rewardFor(rule.achievementId),
      priority: rulePriority(rule),
      unlocked: unlockStatus(rule.achievementId)
    }));

    let filtered = decorated;
    if (!state.showUnlocked && state.save) filtered = decorated.filter((x) => x.unlocked !== true);

    filtered.sort((a, b) => {
      if (state.sort === 'priority') {
        const pd = PRIORITY_SCORE[b.priority] - PRIORITY_SCORE[a.priority];
        if (pd) return pd;
      }
      if (state.view === 'character') {
        return a.rule.defaultOrder - b.rule.defaultOrder || a.rule.achievementId - b.rule.achievementId;
      }
      const ca = characters.get(a.rule.characterId)?.order ?? 999;
      const cb = characters.get(b.rule.characterId)?.order ?? 999;
      return ca - cb || a.rule.achievementId - b.rule.achievementId;
    });
    return filtered;
  }

  function entityIconButton(item, isChar, activeId) {
    const active = item.id === activeId ? ' active' : '';
    const urls = isChar ? [characterLocalImage(item), item.image] : bossImage(item);
    const image = safeImage(urls, 'selector-thumb');
    return `<button type="button" class="entity-icon-card${active}" data-entity="${esc(item.id)}" aria-label="${esc(item.name)}" title="${esc(item.name)}">${image}</button>`;
  }

  function renderEntityGrid() {
    const isChar = state.view === 'character';
    const activeId = isChar ? state.selectedCharacterId : state.selectedBossId;
    el.selectorKicker.textContent = isChar ? '角色' : 'BOSS';
    el.selectorTitle.textContent = isChar ? '选择角色' : '选择 Boss';
    el.selectionSummary.textContent = isChar ? `${DATA.characters.length} 个角色` : `${DATA.bosses.length} 个目标`;

    if (isChar) {
      const normal = DATA.characters.filter((item) => !item.tainted);
      const tainted = DATA.characters.filter((item) => item.tainted);
      el.grid.className = 'entity-groups';
      el.grid.innerHTML = `
        <div class="entity-group">
          <div class="entity-group-label">表角色</div>
          <div class="entity-icon-row">${normal.map((item) => entityIconButton(item, true, activeId)).join('')}</div>
        </div>
        <div class="entity-group">
          <div class="entity-group-label">里角色</div>
          <div class="entity-icon-row">${tainted.map((item) => entityIconButton(item, true, activeId)).join('')}</div>
        </div>`;
    } else {
      el.grid.className = 'entity-groups';
      el.grid.innerHTML = `<div class="entity-group"><div class="entity-icon-row boss-selector-row">${DATA.bosses.map((item) => entityIconButton(item, false, activeId)).join('')}</div></div>`;
    }

    el.grid.querySelectorAll('[data-entity]').forEach((button) => {
      button.addEventListener('click', () => {
        if (isChar) state.selectedCharacterId = button.dataset.entity;
        else state.selectedBossId = button.dataset.entity;
        render();
      });
    });
  }

  function renderHeader() {
    if (state.view === 'challenge') {
      el.tableHead.innerHTML = '<tr><th>挑战 ID</th><th>挑战前置成就</th><th>挑战解锁成就 / 道具</th><th>道具描述</th><th>是否解锁</th><th class="options-column" aria-label="选项"></th></tr>';
      return;
    }
    const isChar = state.view === 'character';
    el.tableHead.innerHTML = isChar
      ? '<tr><th>Boss 图像和名字</th><th>解锁道具 / 奖励</th><th>道具效果</th><th>是否解锁</th><th class="options-column" aria-label="选项"></th></tr>'
      : '<tr><th>角色图像和名字</th><th>解锁道具 / 奖励</th><th>道具效果</th><th>是否解锁</th><th class="options-column" aria-label="选项"></th></tr>';
  }

  function targetCell(rule) {
    if (state.view === 'character') {
      const units = rule.bossIds.map((id) => {
        const boss = bosses.get(id);
        return `<span class="boss-unit">${safeImage(bossImage(boss), 'boss-thumb')}<strong>${esc(boss.name)}</strong></span>`;
      }).join('');
      return `<div class="target-cell"><div><div class="boss-stack">${units}</div>${requirementText(rule)}</div></div>`;
    }
    const char = characters.get(rule.characterId);
    return `<div class="target-cell">${safeImage([characterLocalImage(char), char.image], 'entity-thumb')}<div><strong>${esc(char.name)}</strong>${requirementText(rule, state.selectedBossId)}</div></div>`;
  }

  function rowMenuButton(kind, id, priority) {
    return `<button type="button" class="row-menu-button" data-priority-kind="${esc(kind)}" data-priority-id="${esc(id)}" data-current-priority="${esc(priority)}" aria-label="修改优先级" title="修改优先级">&#8942;</button>`;
  }

  function challengeRows() {
    let rows = CHALLENGES.map((challenge) => ({
      challenge,
      priority: challengePriority(challenge.challengeId),
      prerequisiteUnlocked: challenge.prerequisiteAchievementId == null ? true : unlockStatus(challenge.prerequisiteAchievementId),
      unlocked: unlockStatus(challenge.rewardAchievementId)
    }));
    if (!state.showUnlocked && state.save) rows = rows.filter((x) => x.unlocked !== true);
    rows.sort((a, b) => {
      if (state.sort === 'priority') {
        const pd = PRIORITY_SCORE[b.priority] - PRIORITY_SCORE[a.priority];
        if (pd) return pd;
      }
      return a.challenge.challengeId - b.challenge.challengeId;
    });
    return rows;
  }

  function challengePrerequisiteCell(challenge, unlocked) {
    const aid = challenge.prerequisiteAchievementId;
    if (aid == null) return '<div class="prerequisite-cell"><span class="status-badge unlocked">无需前置</span></div>';
    const wikiUrl = `https://isaac.huijiwiki.com/wiki/${encodeURIComponent('成就')}/${aid}`;
    return `<div class="prerequisite-cell">
      <span class="achievement-sprite compact" aria-hidden="true" style="--ach-x:${-((aid - 1) % ACHIEVEMENT_SPRITE.columns) * ACHIEVEMENT_SPRITE.cell}px;--ach-y:${-Math.floor((aid - 1) / ACHIEVEMENT_SPRITE.columns) * ACHIEVEMENT_SPRITE.cell}px"></span>
      <div><a class="reward-link" href="${esc(wikiUrl)}" target="_blank" rel="noopener noreferrer">成就 #${aid}</a><div class="meta-line">${unlocked === true ? '挑战已开放' : unlocked === false ? '挑战尚未开放' : '读取存档后判断是否开放'}</div></div>
      ${statusBadge(unlocked)}
    </div>`;
  }

  function renderChallengeRows() {
    const rows = challengeRows();
    if (!rows.length) {
      const isFiltered = !state.showUnlocked && state.save;
      const message = isFiltered ? '推荐挑战已经全部完成 🎉' : '当前没有挑战数据';
      const detail = isFiltered ? '打开“显示已解锁”可以重新查看完整挑战列表。' : '请检查 data/challenges.js 是否正确加载。';
      el.tableBody.innerHTML = `<tr class="empty-state"><td colspan="6"><strong>${message}</strong><span>${detail}</span></td></tr>`;
      return;
    }

    el.tableBody.innerHTML = rows.map(({ challenge, priority, prerequisiteUnlocked, unlocked }) => {
      const rewardImage = achievementSprite(challenge.rewardAchievementId);
      const rewardWiki = `https://isaac.huijiwiki.com/wiki/${encodeURIComponent('成就')}/${challenge.rewardAchievementId}`;
      const challengeWiki = `https://isaac.huijiwiki.com/wiki/${encodeURIComponent('挑战')}/${challenge.challengeId}`;
      const effectEntry = EFFECTS[String(challenge.rewardAchievementId)] || null;
      const rewardName = effectEntry?.name || challenge.rewardName;
      const effectText = effectEntry?.effect || challenge.effect || `解锁「${rewardName}」这一非收藏道具 / 机制内容。`;
      return `<tr class="unlock-row priority-${priority}">
        <td><div class="challenge-id-cell"><a class="challenge-id-link" href="${esc(challengeWiki)}" target="_blank" rel="noopener noreferrer">#${challenge.challengeId}</a>${priorityPill(priority)}</div></td>
        <td>${challengePrerequisiteCell(challenge, prerequisiteUnlocked)}</td>
        <td><div class="reward-cell">${rewardImage}<div><div class="reward-name"><a class="reward-link" href="${esc(rewardWiki)}" target="_blank" rel="noopener noreferrer">${esc(rewardName)}</a></div><div class="meta-line">奖励成就 ID #${challenge.rewardAchievementId}</div></div></div></td>
        <td><div class="effect-text">${esc(effectText)}</div></td>
        <td>${statusBadge(unlocked)}</td>
        <td class="row-options">${rowMenuButton('challenge', challenge.challengeId, priority)}</td>
      </tr>`;
    }).join('');
  }

  function renderRows() {
    closePriorityMenu();
    if (state.view === 'challenge') {
      renderChallengeRows();
      return;
    }
    const rows = ruleRows();
    if (!rows.length) {
      const isFiltered = !state.showUnlocked && state.save;
      const message = isFiltered ? '这一项的相关奖励已全部解锁 🎉' : '当前选择没有对应的解锁规则';
      const detail = isFiltered ? '打开“显示已解锁”可以重新查看完整列表。' : '数据模型支持空列表，不会影响其他页面。';
      el.tableBody.innerHTML = `<tr class="empty-state"><td colspan="5"><strong>${message}</strong><span>${detail}</span></td></tr>`;
      return;
    }

    el.tableBody.innerHTML = rows.map(({ rule, reward, priority, unlocked }) => {
      const rewardImage = achievementSprite(rule.achievementId);
      const fallbackEffect = isBabyReward(reward.name) ? '' : `解锁「${reward.name}」这一非收藏道具 / 机制内容。`;
      const rawEffectText = reward.effect || fallbackEffect;
      const effectText = rawEffectText && String(reward.source || '').startsWith('eid-') ? String(rawEffectText).replace(/；\s*/g, '\n') : rawEffectText;
      const effect = effectText ? `<div class="effect-text">${esc(effectText)}</div>` : '<div class="effect-text effect-missing">效果说明待补充</div>';
      const wikiUrl = `https://isaac.huijiwiki.com/wiki/${encodeURIComponent('成就')}/${rule.achievementId}`;
      return `<tr class="unlock-row priority-${priority}">
        <td>${targetCell(rule)}</td>
        <td><div class="reward-cell">${rewardImage}<div><div class="reward-name"><a class="reward-link" href="${esc(wikiUrl)}" target="_blank" rel="noopener noreferrer">${esc(reward.name)}</a>${priorityPill(priority)}</div><div class="meta-line">成就 ID #${rule.achievementId}</div></div></div></td>
        <td>${effect}</td>
        <td>${statusBadge(unlocked)}</td>
        <td class="row-options">${rowMenuButton('rule', rule.id, priority)}</td>
      </tr>`;
    }).join('');
  }

  function sortedAchievementRows(entries) {
    let rows = entries.map((entry, order) => ({
      entry,
      order,
      priority: achievementPriority(entry.achievementId),
      unlocked: unlockStatus(entry.achievementId)
    }));
    if (!state.showUnlocked && state.save) rows = rows.filter((row) => row.unlocked !== true);
    rows.sort((a, b) => {
      if (state.sort === 'priority') {
        const difference = PRIORITY_SCORE[b.priority] - PRIORITY_SCORE[a.priority];
        if (difference) return difference;
      }
      return a.order - b.order;
    });
    return rows;
  }

  function achievementReward(entry) {
    if (!entry.rewardName) return '<span class="effect-missing">无额外奖励</span>';
    const effect = entry.rewardEffect
      ? `<div class="achievement-reward-effect">${esc(entry.rewardEffect)}</div>`
      : '';
    return `<div class="achievement-reward"><strong>${esc(entry.rewardName)}</strong>${effect}</div>`;
  }

  function achievementTable(entries, { includeIsaac = false, characterStartIndex = null, showReward = true } = {}) {
    const rows = sortedAchievementRows(entries);
    const isaac = DATA.characters[0];
    const characterByAchievement = characterStartIndex == null
      ? new Map()
      : new Map(entries.map((entry, index) => [entry.achievementId, DATA.characters[characterStartIndex + index]]));
    const isaacRow = includeIsaac && (state.showUnlocked || !state.save)
      ? `<tr class="unlock-row priority-normal default-character-row">
          <td><div class="reward-cell">${safeImage([characterLocalImage(isaac), isaac.image], 'reward-thumb')}<div><div class="reward-name">以撒${priorityPill('normal')}</div><div class="meta-line">无对应成就 ID</div></div></div></td>
          <td><div class="achievement-condition">游戏开始时默认开放。</div></td>${showReward ? '<td><strong>以撒</strong></td>' : ''}<td>${statusBadge(true)}</td><td class="row-options"></td>
        </tr>`
      : '';
    const body = rows.map(({ entry, priority, unlocked }, index) => {
      const groupStart = entry.sequenceGroup && (index === 0 || rows[index - 1].entry.sequenceGroup !== entry.sequenceGroup)
        ? ' sequence-start'
        : '';
      const wikiUrl = `https://isaac.huijiwiki.com/wiki/${encodeURIComponent('成就')}/${entry.achievementId}`;
      const character = characterByAchievement.get(entry.achievementId);
      const icon = character
        ? safeImage([characterLocalImage(character), character.image], 'reward-thumb')
        : achievementSprite(entry.achievementId);
      return `<tr class="unlock-row priority-${priority}${groupStart}">
        <td><div class="reward-cell">${icon}<div><div class="reward-name"><a class="reward-link" href="${esc(wikiUrl)}" target="_blank" rel="noopener noreferrer">${esc(entry.name)}</a>${priorityPill(priority)}</div><div class="meta-line">成就 ID #${entry.achievementId}</div></div></div></td>
        <td><div class="achievement-condition">${esc(entry.condition)}</div></td>
        ${showReward ? `<td>${achievementReward(entry)}</td>` : ''}
        <td>${statusBadge(unlocked)}</td>
        <td class="row-options">${rowMenuButton('achievement', entry.achievementId, priority)}</td>
      </tr>`;
    }).join('');
    const columnCount = showReward ? 5 : 4;
    const empty = !isaacRow && !body
      ? `<tr class="empty-state"><td colspan="${columnCount}"><strong>这一类成就已经全部完成</strong><span>打开“显示已解锁”可以重新查看完整列表。</span></td></tr>`
      : '';
    const rewardHeader = showReward ? '<th>奖励</th>' : '';
    return `<div class="table-wrap achievement-table-wrap"><table class="unlock-table achievement-table${showReward ? '' : ' without-reward'}"><thead><tr><th>成就图标和名称</th><th>解锁条件</th>${rewardHeader}<th>是否解锁</th><th class="options-column" aria-label="选项"></th></tr></thead><tbody>${isaacRow}${body}${empty}</tbody></table></div>`;
  }

  function achievementGraph() {
    const positions = new Map([
      [4, [8, 124]], [234, [118, 124]],
      [34, [228, 48]], [57, [358, 0]], [78, [358, 96]],
      [320, [228, 220]], [407, [338, 220]], [635, [448, 220]]
    ]);
    const arrows = ACHIEVEMENTS.mainEdges.map(([from, to]) => {
      const [x1, y1] = positions.get(from);
      const [x2, y2] = positions.get(to);
      return `<path d="M ${x1 + 36} ${y1 + 36} L ${x2 + 36} ${y2 + 36}" marker-end="url(#achievementArrow)" />`;
    }).join('');
    const nodes = ACHIEVEMENTS.main.map((entry) => {
      const [x, y] = positions.get(entry.achievementId);
      const unlocked = unlockStatus(entry.achievementId);
      const stateClass = unlocked === false ? ' locked' : unlocked === true ? ' unlocked' : '';
      const stateLabel = unlocked === false ? '，未解锁' : unlocked === true ? '，已解锁' : '';
      return `<g class="achievement-graph-item${stateClass}"><title>${esc(entry.name)}，成就 #${entry.achievementId}${stateLabel}</title><rect class="achievement-graph-node" x="${x}" y="${y}" width="72" height="72" rx="6" /><foreignObject x="${x + 4}" y="${y + 4}" width="64" height="64"><div xmlns="http://www.w3.org/1999/xhtml" class="achievement-graph-icon">${achievementSprite(entry.achievementId)}</div></foreignObject></g>`;
    }).join('');
    return `<div class="achievement-graph-wrap"><svg class="achievement-graph" viewBox="0 0 528 292" role="img" aria-label="主线成就解锁流程"><defs><marker id="achievementArrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" /></marker></defs><g class="achievement-graph-edges">${arrows}</g>${nodes}</svg></div>`;
  }

  function achievementSection(title, count, content, extraClass = '') {
    return `<section class="achievement-category ${extraClass}"><div class="achievement-category-heading"><div><span class="section-kicker">其他成就</span><h2>${esc(title)}</h2></div><span>${count} 个成就</span></div>${content}</section>`;
  }

  function renderAchievementRows() {
    const characterColumns = `<div class="achievement-character-columns"><div><h3>表角色</h3>${achievementTable(ACHIEVEMENTS.characters.normal, { includeIsaac: true, characterStartIndex: 1, showReward: false })}</div><div><h3>里角色</h3>${achievementTable(ACHIEVEMENTS.characters.tainted, { characterStartIndex: 17, showReward: false })}</div></div>`;
    el.achievementResults.innerHTML = [
      achievementSection('主线成就', ACHIEVEMENTS.main.length, achievementGraph() + achievementTable(ACHIEVEMENTS.main), 'main-achievements'),
      achievementSection('角色解锁类', ACHIEVEMENTS.characters.normal.length + ACHIEVEMENTS.characters.tainted.length, characterColumns),
      achievementSection('次数 / 累计型成就', ACHIEVEMENTS.cumulative.length, achievementTable(ACHIEVEMENTS.cumulative)),
      achievementSection('完成类成就', ACHIEVEMENTS.completion.length, achievementTable(ACHIEVEMENTS.completion))
    ].join('');
  }

  function render() {
    document.querySelectorAll('.page-tab').forEach((b) => b.classList.toggle('active', b.dataset.view === state.view));
    document.querySelectorAll('.segment').forEach((b) => b.classList.toggle('active', b.dataset.sort === state.sort));
    el.showUnlocked.checked = state.showUnlocked;
    renderProfileControls();
    const hasSelector = state.view === 'character' || state.view === 'boss';
    const isAchievement = state.view === 'achievement';
    el.selectorSection.hidden = !hasSelector;
    el.standardResults.hidden = isAchievement;
    el.achievementResults.hidden = !isAchievement;
    if (hasSelector) renderEntityGrid();
    if (isAchievement) renderAchievementRows();
    else {
      renderHeader();
      renderRows();
    }
  }

  // ---------- Priority menu ----------

  function closePriorityMenu() {
    state.menuTarget = null;
    el.priorityMenu.hidden = true;
    el.priorityMenu.innerHTML = '';
  }

  function openPriorityMenu(button) {
    const kind = button.dataset.priorityKind;
    const id = button.dataset.priorityId;
    const current = normalizePriority(button.dataset.currentPriority);
    state.menuTarget = { kind, id };
    el.priorityMenu.innerHTML = ['strong', 'recommended', 'normal'].map((priority) => (
      `<button type="button" class="priority-menu-item${priority === current ? ' active' : ''}" data-set-priority="${priority}" role="menuitem"><span class="priority-menu-dot ${priority}"></span><span>${PRIORITY_LABEL[priority]}</span>${priority === current ? '<span class="priority-menu-check">✓</span>' : ''}</button>`
    )).join('');
    el.priorityMenu.hidden = false;

    const rect = button.getBoundingClientRect();
    const menuRect = el.priorityMenu.getBoundingClientRect();
    let left = rect.right - menuRect.width;
    let top = rect.bottom + 5;
    left = Math.max(8, Math.min(left, window.innerWidth - menuRect.width - 8));
    if (top + menuRect.height > window.innerHeight - 8) top = rect.top - menuRect.height - 5;
    el.priorityMenu.style.left = `${left}px`;
    el.priorityMenu.style.top = `${Math.max(8, top)}px`;
  }

  // ---------- Events ----------

  document.querySelectorAll('.page-tab').forEach((button) => {
    button.addEventListener('click', () => { state.view = button.dataset.view; render(); });
  });

  document.querySelectorAll('.segment').forEach((button) => {
    button.addEventListener('click', () => {
      state.sort = button.dataset.sort;
      persistUiPreferences();
      if (state.view === 'achievement') renderAchievementRows();
      else renderRows();
      document.querySelectorAll('.segment').forEach((b) => b.classList.toggle('active', b.dataset.sort === state.sort));
    });
  });

  el.showUnlocked.addEventListener('change', () => {
    state.showUnlocked = el.showUnlocked.checked;
    persistUiPreferences();
    if (state.view === 'achievement') renderAchievementRows();
    else renderRows();
  });
  el.loadSaveBtn.addEventListener('click', () => el.saveInput.click());
  el.clearSaveBtn.addEventListener('click', clearPersistedSave);
  el.saveInput.addEventListener('change', () => loadSave(el.saveInput.files?.[0]));

  el.profileSelect.addEventListener('change', () => {
    if (el.profileSelect.value !== '__current__') switchBuiltinProfile(el.profileSelect.value);
  });
  el.importProfileBtn.addEventListener('click', () => el.profileImportInput.click());
  el.exportProfileBtn.addEventListener('click', exportCurrentProfile);
  el.profileImportInput.addEventListener('change', () => importProfileFile(el.profileImportInput.files?.[0]));

  function handleRowMenuClick(event) {
    const button = event.target.closest('.row-menu-button');
    if (!button) return;
    event.stopPropagation();
    if (!el.priorityMenu.hidden && state.menuTarget?.kind === button.dataset.priorityKind && String(state.menuTarget?.id) === String(button.dataset.priorityId)) {
      closePriorityMenu();
    } else {
      openPriorityMenu(button);
    }
  }

  el.tableBody.addEventListener('click', handleRowMenuClick);
  el.achievementResults.addEventListener('click', handleRowMenuClick);

  el.priorityMenu.addEventListener('click', (event) => {
    const item = event.target.closest('[data-set-priority]');
    if (!item || !state.menuTarget) return;
    const priority = item.dataset.setPriority;
    if (state.menuTarget.kind === 'rule') setRulePriority(state.menuTarget.id, priority);
    else if (state.menuTarget.kind === 'challenge') setChallengePriority(state.menuTarget.id, priority);
    else if (state.menuTarget.kind === 'achievement') setAchievementPriority(state.menuTarget.id, priority);
  });

  document.addEventListener('click', (event) => {
    if (!el.priorityMenu.hidden && !el.priorityMenu.contains(event.target) && !event.target.closest('.row-menu-button')) closePriorityMenu();
  });

  document.querySelectorAll('[data-copy-path]').forEach((node) => {
    const handleCopy = async () => {
      const text = node.dataset.copyPath || node.textContent || '';
      const success = await copyTextCompat(text);
      if (success) {
        showToast('路径已复制到剪贴板');
        return;
      }
      showManualCopyDialog(text);
      showToast('请手动复制路径');
    };

    node.addEventListener('click', handleCopy);
    node.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      handleCopy();
    });
  });

  window.addEventListener('resize', closePriorityMenu);
  window.addEventListener('scroll', closePriorityMenu, true);

  ['dragenter', 'dragover'].forEach((eventName) => el.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    el.dropZone.classList.add('dragging');
  }));
  ['dragleave', 'drop'].forEach((eventName) => el.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    el.dropZone.classList.remove('dragging');
  }));
  el.dropZone.addEventListener('drop', (event) => loadSave(event.dataTransfer?.files?.[0]));

  async function initApp() {
    await initStorage();
    restoreUiPreferences();
    initializeRecommendationProfile();
    restorePersistedSave();
    render();
  }

  initApp().catch((error) => {
    console.error('初始化失败：', error);
    restoreUiPreferences();
    initializeRecommendationProfile();
    restorePersistedSave();
    render();
  });
})();
