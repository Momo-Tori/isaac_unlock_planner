(function () {
  'use strict';

  const DATA = window.ISAAC_UNLOCK_DATA;
  const RECOMMENDATIONS = window.ISAAC_RECOMMENDATIONS?.entries || {};
  const EFFECTS = window.ISAAC_EFFECTS?.entries || {};
  const CHALLENGES = window.ISAAC_CHALLENGE_DATA?.entries || [];
  const OVERRIDES = window.ISAAC_OVERRIDES || {};
  const Parser = window.IsaacSaveParser;
  // app.js 自身通过 ?v=... 加载；本地图片沿用同一版本号，避免 GitHub Pages 更新图片后仍命中旧缓存。
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
  if (!DATA || !Parser) throw new Error('页面数据或存档解析器未加载。');

  const PRIORITY_SCORE = { strong: 3, recommended: 2, normal: 1 };
  const PRIORITY_LABEL = { strong: '强烈推荐', recommended: '推荐', normal: '普通' };
  const byId = (items) => new Map(items.map((x) => [x.id, x]));
  const characters = byId(DATA.characters);
  const bosses = byId(DATA.bosses);

  const state = {
    view: 'character',
    selectedCharacterId: DATA.characters[0].id,
    selectedBossId: DATA.bosses[0].id,
    sort: 'priority',
    showUnlocked: true,
    save: null,
    saveName: ''
  };

  const el = {
    selectorSection: document.getElementById('selectorSection'),
    grid: document.getElementById('entityGrid'),
    selectorKicker: document.getElementById('selectorKicker'),
    selectorTitle: document.getElementById('selectorTitle'),
    selectionSummary: document.getElementById('selectionSummary'),
    tableHead: document.getElementById('tableHead'),
    tableBody: document.getElementById('tableBody'),
    showUnlocked: document.getElementById('showUnlocked'),
    saveInput: document.getElementById('saveInput'),
    loadSaveBtn: document.getElementById('loadSaveBtn'),
    saveStatus: document.getElementById('saveStatus'),
    dropZone: document.getElementById('dropZone')
  };

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
    const recommendation = RECOMMENDATIONS[key] || {};
    const effectData = EFFECTS[key] || {};
    const override = OVERRIDES[key] || OVERRIDES[aid] || {};
    const merged = { ...base, ...recommendation, ...effectData, ...override };
    const priority = ['strong', 'recommended', 'normal'].includes(merged.priority) ? merged.priority : 'normal';
    return {
      ...merged,
      priority,
      name: merged.name || `成就 #${aid}`,
      image: merged.image || base.image || null,
      effect: merged.effect || '',
      condition: base.condition || merged.condition || ''
    };
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

  function ruleRows() {
    let rules;
    if (state.view === 'character') {
      rules = DATA.unlockRules.filter((r) => r.characterId === state.selectedCharacterId);
    } else {
      rules = DATA.unlockRules.filter((r) => r.bossIds.includes(state.selectedBossId));
    }

    const decorated = rules.map((rule) => {
      const reward = rewardFor(rule.achievementId);
      const unlocked = unlockStatus(rule.achievementId);
      return { rule, reward, unlocked };
    });

    let filtered = decorated;
    if (!state.showUnlocked && state.save) filtered = decorated.filter((x) => x.unlocked !== true);

    filtered.sort((a, b) => {
      if (state.sort === 'priority') {
        const pd = PRIORITY_SCORE[b.reward.priority] - PRIORITY_SCORE[a.reward.priority];
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
      el.tableHead.innerHTML = '<tr><th>挑战 ID</th><th>挑战前置成就</th><th>挑战解锁成就 / 道具</th><th>道具描述</th><th>是否解锁</th></tr>';
      return;
    }
    const isChar = state.view === 'character';
    el.tableHead.innerHTML = isChar
      ? '<tr><th>Boss 图像和名字</th><th>解锁道具 / 奖励</th><th>道具效果</th><th>是否解锁</th></tr>'
      : '<tr><th>角色图像和名字</th><th>解锁道具 / 奖励</th><th>道具效果</th><th>是否解锁</th></tr>';
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

  function challengeRows() {
    let rows = CHALLENGES.map((challenge) => ({
      challenge,
      prerequisiteUnlocked: challenge.prerequisiteAchievementId == null
        ? true
        : unlockStatus(challenge.prerequisiteAchievementId),
      unlocked: unlockStatus(challenge.rewardAchievementId)
    }));

    if (!state.showUnlocked && state.save) rows = rows.filter((x) => x.unlocked !== true);

    rows.sort((a, b) => {
      if (state.sort === 'priority') {
        const pd = PRIORITY_SCORE[b.challenge.priority] - PRIORITY_SCORE[a.challenge.priority];
        if (pd) return pd;
      }
      return a.challenge.challengeId - b.challenge.challengeId;
    });
    return rows;
  }

  function challengePrerequisiteCell(challenge, unlocked) {
    const aid = challenge.prerequisiteAchievementId;
    if (aid == null) {
      return '<div class="prerequisite-cell"><span class="status-badge unlocked">无需前置</span></div>';
    }
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
      el.tableBody.innerHTML = `<tr class="empty-state"><td colspan="5"><strong>${message}</strong><span>${detail}</span></td></tr>`;
      return;
    }

    el.tableBody.innerHTML = rows.map(({ challenge, prerequisiteUnlocked, unlocked }) => {
      const rewardImage = achievementSprite(challenge.rewardAchievementId);
      const rewardWiki = `https://isaac.huijiwiki.com/wiki/${encodeURIComponent('成就')}/${challenge.rewardAchievementId}`;
      const challengeWiki = `https://isaac.huijiwiki.com/wiki/${encodeURIComponent('挑战')}/${challenge.challengeId}`;
      const effect = challenge.effect
        ? `<div class="effect-text">${esc(challenge.effect)}</div>`
        : `<div class="effect-text">解锁「${esc(challenge.rewardName)}」这一非收藏道具 / 机制内容。</div>`;
      return `<tr class="unlock-row priority-${challenge.priority}">
        <td><div class="challenge-id-cell"><a class="challenge-id-link" href="${esc(challengeWiki)}" target="_blank" rel="noopener noreferrer">#${challenge.challengeId}</a>${priorityPill(challenge.priority)}</div></td>
        <td>${challengePrerequisiteCell(challenge, prerequisiteUnlocked)}</td>
        <td><div class="reward-cell">${rewardImage}<div><div class="reward-name"><a class="reward-link" href="${esc(rewardWiki)}" target="_blank" rel="noopener noreferrer">${esc(challenge.rewardName)}</a></div><div class="meta-line">奖励成就 ID #${challenge.rewardAchievementId}</div></div></div></td>
        <td>${effect}</td>
        <td>${statusBadge(unlocked)}</td>
      </tr>`;
    }).join('');
  }

  function renderRows() {
    if (state.view === 'challenge') {
      renderChallengeRows();
      return;
    }
    const rows = ruleRows();
    if (!rows.length) {
      const isFiltered = !state.showUnlocked && state.save;
      const message = isFiltered ? '这一项的相关奖励已全部解锁 🎉' : '当前选择没有对应的解锁规则';
      const detail = isFiltered ? '打开“显示已解锁”可以重新查看完整列表。' : '数据模型支持空列表，不会影响其他页面。';
      el.tableBody.innerHTML = `<tr class="empty-state"><td colspan="4"><strong>${message}</strong><span>${detail}</span></td></tr>`;
      return;
    }

    el.tableBody.innerHTML = rows.map(({ rule, reward, unlocked }) => {
      const rewardImage = achievementSprite(rule.achievementId);
      const fallbackEffect = isBabyReward(reward.name)
        ? ''
        : `解锁「${reward.name}」这一非收藏道具 / 机制内容。`;
      const rawEffectText = reward.effect || fallbackEffect;
      // EID uses separators between effect clauses. Render them as separate lines
      // instead of leaving a dense Chinese semicolon-delimited paragraph.
      const effectText = rawEffectText && String(reward.source || '').startsWith('eid-')
        ? String(rawEffectText).replace(/；\s*/g, '\n')
        : rawEffectText;
      const effect = effectText
        ? `<div class="effect-text">${esc(effectText)}</div>`
        : '<div class="effect-text effect-missing">效果说明待补充</div>';
      const wikiUrl = `https://isaac.huijiwiki.com/wiki/${encodeURIComponent('成就')}/${rule.achievementId}`;
      return `<tr class="unlock-row priority-${reward.priority}">
        <td>${targetCell(rule)}</td>
        <td><div class="reward-cell">${rewardImage}<div><div class="reward-name"><a class="reward-link" href="${esc(wikiUrl)}" target="_blank" rel="noopener noreferrer">${esc(reward.name)}</a>${priorityPill(reward.priority)}</div><div class="meta-line">成就 ID #${rule.achievementId}</div></div></div></td>
        <td>${effect}</td>
        <td>${statusBadge(unlocked)}</td>
      </tr>`;
    }).join('');
  }

  function render() {
    document.querySelectorAll('.page-tab').forEach((b) => b.classList.toggle('active', b.dataset.view === state.view));
    document.querySelectorAll('.segment').forEach((b) => b.classList.toggle('active', b.dataset.sort === state.sort));
    el.showUnlocked.checked = state.showUnlocked;
    const isChallenge = state.view === 'challenge';
    el.selectorSection.hidden = isChallenge;
    if (!isChallenge) renderEntityGrid();
    renderHeader();
    renderRows();
  }

  function setSaveStatus(type, title, detail) {
    el.saveStatus.innerHTML = `<span class="status-dot ${type}"></span><div><strong>${esc(title)}</strong><small>${esc(detail)}</small></div>`;
  }

  async function loadSave(file) {
    if (!file) return;
    try {
      const buffer = await file.arrayBuffer();
      const parsed = Parser.parsePersistentGameData(buffer);
      state.save = parsed;
      state.saveName = file.name;
      setSaveStatus('ready', file.name, `已解锁 ${parsed.unlockedCount} 个成就 · 成就块 ${parsed.achievementCount} 项`);
      render();
    } catch (error) {
      state.save = null;
      state.saveName = '';
      setSaveStatus('error', '读取失败', error?.message || String(error));
      render();
    }
  }

  document.querySelectorAll('.page-tab').forEach((button) => {
    button.addEventListener('click', () => { state.view = button.dataset.view; render(); });
  });
  document.querySelectorAll('.segment').forEach((button) => {
    button.addEventListener('click', () => { state.sort = button.dataset.sort; renderRows(); document.querySelectorAll('.segment').forEach((b) => b.classList.toggle('active', b.dataset.sort === state.sort)); });
  });
  el.showUnlocked.addEventListener('change', () => { state.showUnlocked = el.showUnlocked.checked; renderRows(); });
  el.loadSaveBtn.addEventListener('click', () => el.saveInput.click());
  el.saveInput.addEventListener('change', () => loadSave(el.saveInput.files?.[0]));

  ['dragenter', 'dragover'].forEach((eventName) => el.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault(); el.dropZone.classList.add('dragging');
  }));
  ['dragleave', 'drop'].forEach((eventName) => el.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault(); el.dropZone.classList.remove('dragging');
  }));
  el.dropZone.addEventListener('drop', (event) => loadSave(event.dataTransfer?.files?.[0]));

  render();
})();
