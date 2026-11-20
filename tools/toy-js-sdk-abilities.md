# Toy JS SDK 能力清单

> 更新时间：2026-11-17

Toy JS SDK 为你的 Toy 页面提供与 B站 App / Web 环境交互的能力。

> ⚠️ **数据使用限制**：SDK 仅在用户确认后向 Toy 页面返回 getUserProfile 约定的头像、昵称和当前 Toy 内用户标识；不会向 Toy 提供 UID/MID、登录令牌、确认挑战值或可用于跨 Toy 识别的真实账号信息。其他能力仅返回各自文档约定的业务字段。

## 接入方式

在 HTML 的 `<head>` 中添加：

```html
<script src="//s1.hdslb.com/bfs/seed/toy/app/sdk/toy-sdk.js"></script>
```

加载后全局可用 `window.toy` 对象；除同步返回取消函数的 `onContainerChange` / `onPlayerChange` / `onPageClose` 外，其余方法返回 Promise。用户与作者数据、云存储、共享存档、排行榜和玩家输入内容检测在 B站 App/Web 行为一致；保存图片、关闭页面、拉起分享、分享图片、容器控制、播放器控制和页面关闭通知等能力仅在 B站 App 内可用，调用前建议先用 `isSupport` 判断。

## 能力列表

### toy.isSupport(ability)

判断当前环境是否支持指定能力。

参数：
- `ability`: string（必填）- 能力名称：navigate | saveImageToAlbum | share | getQrCode | sharePicture | closeBrowser | getUserProfile | getCloudStorage | setCloudStorage | removeCloudStorage | getAuthorProfile | getAuthorVideos | getAuthorRelation | getVideoUserActions | submitScore | getRankList | getMyRank | requestCamera | requestMicrophone | stopMedia | onContainerChange | getContainerState | setContainerMode | onPlayerChange | getPlayerState | setPlayerState | onPageClose | checkInputSafety | getSharedStorage | setSharedStorage | removeSharedStorage | getChargeUnlock | openChargePanel | getAnnualReport

返回值：`Promise<boolean>`

```js
const ok = await toy.isSupport('saveImageToAlbum')
if (ok) {
  toy.saveImageToAlbum({ url: '...' })
}
```

### toy.navigate(req)

跳转到指定页面（需用户手势触发）。

参数：
- `type`: string（必填）- 页面类型：video | space | search | opus | tribee | toy
- `id`: string（必填）- 资源 ID，如视频 BV 号、用户 mid、动态 id
- `extra`: Record<string, string>（可选）- 额外参数，透传给目标页面

返回值：`Promise<void>`

```js
await toy.navigate({
  type: 'video',
  id: 'BV1Hh411S7Ys',
  extra: { from: 'toy' }
})
```

### toy.saveImageToAlbum(req)

保存图片到相册（仅 B站 App 内）。

参数：
- `url`: string（可选）- 网络图片地址，由客户端下载后保存，不受 base64 体积影响；与 base64Data 二选一，同时传优先用 url
- `base64Data`: string（可选）- base64 图片数据，可带 data:image/...;base64, 前缀，也可只传纯 base64；与 url 二选一。上限 5MB，指 base64 字符串本身的长度（含前缀与换行等空白），不是解码后的原图大小；超限直接抛错。未超限也建议控制在 2M 以内：字符串越大，保存越慢、内存占用越高，更大的图请改用 url
- `hintMsg`: string（可选）- 申请相册权限时的提示文案

返回值：`Promise<{ localPath: string }>`

```js
await toy.saveImageToAlbum({
  url: 'https://i0.hdslb.com/bfs/archive/example.jpg',
  hintMsg: '需要相册权限来保存图片'
})
```

### toy.share(req)

拉起 B站 App 的分享面板（仅 B站 App 内）。只传相对当前 Toy 的 path，完整分享链接由平台生成，Toy 不能自行指定完整 URL。

参数：
- `path`: string（必填）- 相对当前 Toy 页面根的路径，可带 query（如 result.html?score=100）。只能指向当前 Toy 内的页面；传绝对 URL 或用 ../ 越界到其他 Toy / 外域会抛 invalid_param

返回值：`Promise<void>`

```js
// path 相对当前 Toy 的页面根（/toy/<slug>/）解析
await toy.share({ path: 'result.html?score=100' })
// 实际分享链接为 https://www.bilibili.com/toy/<当前slug>/result.html?score=100
```

### toy.getQrCode(req)

生成指向当前 Toy 内某个页面的二维码，返回可直接用作 img.src 的 PNG base64 图片。用途不限于分享：跨设备接力（PC 上扫码到手机继续玩）、结算页海报、线下展示都适用。两个入参都可省略，不传即当前 Toy 首页的二维码。只能编码当前 Toy 内的页面链接、不能编码任意文本：二维码内容由平台生成，Toy 不能自行指定完整 URL。如需为任意字符串生成二维码，请自行在 Toy 内打包二维码库。

参数：
- `path`: string（可选）- 相对当前 Toy 页面根的路径，可带 query（如 result.html?score=100）。不传或传空串时指向当前 Toy 首页 index.html。只能指向当前 Toy 内的页面；传绝对 URL 或用 ../ 越界到其他 Toy / 外域会抛 invalid_param
- `size`: number（可选）- 二维码边长（像素），取值区间 [80, 1024] 的整数。不传默认 320，越界或非整数抛 invalid_param

返回值：`Promise<{ base64: string, url: string }>`

```js
// 不传参数即当前 Toy 首页的二维码
const { base64, url } = await toy.getQrCode()
document.querySelector('#qr').src = base64

// 指向 Toy 内某个页面
const result = await toy.getQrCode({ path: 'result.html?score=100' })
// url 为二维码实际编码的链接：https://www.bilibili.com/toy/<当前slug>/result.html?score=100
```

### toy.sharePicture(req)

分享图片本身，拉起原生分享面板（仅 B站 App 内）。与 share 的区别：share 分享的是链接，图片只作卡片配图；sharePicture 分享的就是这张图，适合成绩海报、表情包等场景。字段形制与 saveImageToAlbum 一致，两个能力可共用同一份图片数据。

参数：
- `url`: string（可选）- 网络图片地址；与 base64Data 至少传一个，同时传时以 url 为准。图片较大时优先用 url
- `base64Data`: string（可选）- base64 图片数据，最大 2M，超出由端侧拒绝；url 与 base64Data 都不传会抛 invalid_param

返回值：`Promise<void>`

```js
// 分享网络图片
await toy.sharePicture({ url: 'https://i0.hdslb.com/bfs/xxx.png' })

// 分享 canvas 生成的图片
const base64Data = canvas.toDataURL('image/png')
await toy.sharePicture({ base64Data })
```

### toy.closeBrowser()

关闭当前 WebView 容器（仅 B站 App 内）。

返回值：`Promise<void>`

```js
await toy.closeBrowser()
```

### toy.getUserProfile()

获取当前用户头像、昵称和当前 Toy 内的稳定假名标识。OpenID 模式启用后，已有未过期的 profile v1/v2 授权直接复用、不重复弹窗；没有有效授权时，首次调用需由用户操作触发，并由平台展示“获取你的昵称、头像和当前 Toy 内用户标识”数据确认弹窗，正文为“你的 B站昵称、头像和仅用于当前 Toy 的用户标识，将用于当前 Toy 内展示和关联数据；不会向 Toy 提供你的 UID，也不能用于跨 Toy 识别。”，接受后写入 v2 授权。模式关闭时省略 toyOpenId。。

返回值：`Promise<{ avatar: string, nickname: string, toyOpenId?: string }>`

```js
const { avatar, nickname, toyOpenId } = await toy.getUserProfile()
// toyOpenId 仅用于当前 Toy 内关联用户，不要写入埋点或公开日志
```

### toy.getAuthorProfile()

获取当前 Toy 作者的公开资料、账号统计、稿件数、充电聚合和粉丝勋章配置，不允许指定作者 ID。

返回值：`Promise<AuthorProfileResp>`

```js
const result = await toy.getAuthorProfile()
if (result.status === 'ok') {
  console.log(result.data.nickname, result.data.follower)
}
```

### toy.getAuthorVideos(req)

批量获取当前 Toy 作者的视频公开信息，含作者以联合投稿（共同创作）身份参与的视频；作者未参与创作或不可见的视频不会返回标题、封面和统计。

参数：
- `videos`: Array<{ aid: number } | { bvid: string }>（必填）- 1–50 项，每项只能传 aid 或 bvid；SDK 去重并保留首次出现顺序

返回值：`Promise<AuthorVideosResp>`

```js
const result = await toy.getAuthorVideos({
  videos: [{ aid: 170001 }, { bvid: 'BV17x411w7KC' }]
})
```

### toy.getAuthorRelation()

获取当前访问用户与当前 Toy 作者的关注、老粉、粉丝勋章状态，以及当前是否正在对该作者进行包月充电。

返回值：`Promise<AuthorRelationResp>`

```js
const result = await toy.getAuthorRelation()
if (result.status === 'ok') {
  console.log(result.data.isFollowing, result.data.hasFanMedal)
}
```

### toy.getVideoUserActions(req)

获取当前访问用户对当前作者视频（含联合投稿参与的视频）的点赞、投币和收藏状态；只校验登录态，不触发用户数据确认弹窗。

参数：
- `aids`: number[]（可选）- 1–50 个正整数 aid；与 videos 二选一（都传或都不传报错）。SDK 去重并保留首次出现顺序
- `videos`: Array<{ aid: number } | { bvid: string }>（可选）- 1–50 项，每项只能传 aid 或 bvid，可混传；与 aids 二选一。bvid 由服务端换算成 aid，aid 与 bvid 指向同一视频时会去重合并为一项

返回值：`Promise<VideoUserActionsResp>`

```js
// 传 aid
const result = await toy.getVideoUserActions({ aids: [170001, 455017605] })
// 或传 bvid（与 getAuthorVideos 同口径，可混传）
const byBvid = await toy.getVideoUserActions({
  videos: [{ bvid: 'BV17x411w7KC' }, { aid: 455017605 }]
})
result.items.forEach(item => {
  // item.aid / item.bvid 恒有；传 videos 时 item.ref 回显你传的那一项
  if (item.status === 'ok') console.log(item.aid, item.bvid, item.liked, item.coinCount, item.favorited)
})
```

### toy.getAnnualReport(req)

读取当前登录用户对 UP 主（通常为当前 Toy 的作者，见返回值 target）的年度数据，UP 主可用于制作「粉丝和 UP 主的年度回忆」类 Toy。

- 因平台存储和计算成本，当前仅提供「用户 - 年度挚爱 UP 主」之间的数据：若 UP 主并非某用户的年度挚爱 UP 主，通常无法返回数据。UP 主在制作 Toy 时，需考虑访问 Toy 的用户没有该数据的情况。
- 接口内置了「当前登录用户 - 年度挚爱 UP 主」的关系查询，UP 主编写 Toy 时直接调用即可。
- 直接返回年度数据，失败时 Promise reject：未登录为 not_logged_in，预览态和外部手机浏览器为 unsupported，数据暂不可用为 http_error。
- 年度数据条目较多，可能存在一个用户部分条目数据为空的情况，请提前准备兜底体验。
- 2026 年年报预计于 2026 年 12 月下旬正式上线，在此之前本接口仅返回示例假数据，仅供制作调试。
- ⚠️ 年报数据将于 2027 年 3 月 31 日下线，之后调用会 reject（http_error），请提前准备兜底内容。

参数：
- `edition`: string（必填）- 期数，四位年份字符串（如 '2026'）。传数字 2026 或其他格式会抛 invalid_param

返回值：`Promise<AnnualReport>`

返回字段：
- `target`: object | null - 年报对象「TA」，一般是当前 Toy 的作者；暂时获取不到时为 null
- `target.nickname`: string - 昵称；暂时获取不到时为空字符串
- `target.avatar`: string - 头像；暂时获取不到时为空字符串
- `first_watch_date`: number | null - 本期第一次看 TA 的日期，unix 秒
- `first_watch_video`: AuthorVideo | null - 第一次看的视频
- `watch_duration`: number - 观看 TA 的时长，单位分钟
- `watch_percentile`: number - 观看时长排名百分位，0 ~ 99.99，越大越靠前
- `watch_month_cnt`: number - 有观看记录的月数，1 ~ 12
- `duration_ratio`: number - 看 TA 的时长占你在 B站总时长的比例，0 ~ 1
- `old_arch_cnt`: number | null - 考古了 TA 多少条旧作（本期之前发布的视频）
- `oldest_arch_date`: number | null - 看过的最早一条视频的发布日期，unix 秒
- `oldest_arch_video`: AuthorVideo | null - 看过的最早一条视频
- `chase_arch_cnt`: number | null - 追更了 TA 多少条本期新视频
- `live_join_cnt`: number - 进入 TA 直播间的场次数
- `up_arch_cnt`: number | null - TA 本期公开投稿数
- `up_live_cnt`: number - TA 本期开播次数
- `n_watch_video`: AuthorVideo | null - N 刷视频：看了 3 次及以上的视频中次数最多的那个
- `n_watch_last_date`: number | null - 最近一次看 N 刷视频的日期，unix 秒
- `n_watch_cnt`: number | null - N 刷次数，最小 3
- `likes_cnt`: number | null - 本期为 TA 点赞次数
- `elec_cnt`: number | null - 本期为 TA 充电次数
- `coin_cnt`: number | null - 本期为 TA 投币枚数
- `interact_cnt`: number | null - 直播间互动次数，仅年度挚爱主播有
- `up_like_reply_cnt`: number | null - 你的评论 / 弹幕被 TA 点赞或回复的次数
- `up_main_area`: string | null - 你和 TA 共同的兴趣领域名；没有共同领域时为空字符串
- `resonance_video`: AuthorVideo | null - 共同领域里你看过的 TA 播放量最高的视频
- `hot_arch_list`: Array - 见证时刻，按优先级升序、最多 5 条；没有时为空数组
- `hot_arch_list[].type`: number - 1 最晚投稿 / 2 最长视频 / 3 人气最高直播 / 4 播放最高 / 5 最近一次每周必看收录 / 6 最近一次上过热门 / 7 点赞最高 / 8 投币最多
- `hot_arch_list[].video`: AuthorVideo - 视频条目的视频信息；直播条目或视频已删除、不可见时缺省
- `hot_arch_list[].watch_date`: number - 观众第一次看这个视频的日期，unix 秒；直播条目缺省
- `hot_arch_list[].live`: object - 直播条目（type 为 3）的场次信息；视频条目或场次不存在时缺省
- `hot_arch_list[].live.live_key`: string - 场次 ID
- `hot_arch_list[].live.room_id`: number - 直播间长号
- `hot_arch_list[].live.title`: string - 直播间当前标题，不是该场次开播时的标题
- `hot_arch_list[].live.cover`: string - 直播间当前封面，不是该场次开播时的封面
- `hot_arch_list[].live.jump_url`: string - 直播间跳转地址
- `hot_arch_list[].live.status`: number - 0 已关播无回放 / 1 直播中 / 2 已关播有回放
- `hot_arch_list[].live.replay_bvid`: string - 回放视频 BV 号；没有回放时缺省
- `fans`: object | null - 直播粉丝关系，实时数据；暂时获取不到时为 null
- `fans.medal`: object | null - 粉丝勋章；未持有时为 null
- `fans.medal.name`: string - 勋章名称
- `fans.medal.level`: number - 勋章等级
- `fans.medal.is_light`: boolean - 是否点亮
- `fans.guard_level`: number - 大航海等级：0 无 / 1 总督 / 2 提督 / 3 舰长
- `fans.accompany_days`: number - 大航海陪伴天数（累计值），0 表示从未陪伴

```js
try {
  const report = await toy.getAnnualReport({ edition: '2026' })
  // 字段为 snake_case。可空字段为 null、计数为 0 时跳过对应内容
  console.log(report.watch_duration, '分钟')
  if (report.first_watch_video) {
    console.log('第一次看的视频：', report.first_watch_video.title, report.first_watch_video.cover)
  }
  report.hot_arch_list.forEach(item => {
    if (item.video) console.log('见证时刻（视频）', item.type, item.video.title)
    if (item.live) console.log('见证时刻（直播）', item.live.title)
  })
  if (report.fans?.medal) console.log('粉丝勋章', report.fans.medal.name, report.fans.medal.level)
} catch (error) {
  if (error.type === 'not_logged_in') {
    // 未登录：引导登录后再看
  } else {
    // unsupported / http_error（含该用户没有 TA 的年度数据）：展示兜底内容
  }
}
```

### toy.getChargeUnlock(req)

判断当前访问用户对当前 Toy 作者的包月充电档位是否达到指定金额，用于决定是否展示付费内容。需平台侧白名单开通、需 shell 渲染模式，预览态返回 unsupported。minPrice 单位是分（1200 = 12 元）。⚠️ 仅充电档位 ≥ 12 元可解锁 Toy 内容；6 元档暂不支持解锁任何内容权益，门槛传 1200 以下不会让 6 元用户拿到内容。

参数：
- `minPrice`: number（必填）- 档位金额，单位分的正整数（12 元传 1200）。不接受 0、负数和小数；上限由平台控制，超限返回 invalid_argument。**建议填 1200**：6 元档（600）不支持解锁任何内容权益

返回值：`Promise<ChargeUnlockResp>`

```js
const result = await toy.getChargeUnlock({ minPrice: 1200 }) // 12 元档

if (result.status === 'ok' && result.data.unlocked) {
  showPaidContent()
} else if (result.status === 'ok') {
  // 已查到，但档位不够：引导去充电
  showPaywall()
} else {
  // unavailable / unauthorized / denied 等都不是「未解锁」，而是「没查成」或「不能查」，
  // 一律按未解锁展示，并提示稍后再试，不要放行内容
  showRetry()
}
```

### toy.openChargePanel(req)

拉起当前 Toy 作者的包月充电收银台，默认选中指定档位。必须在用户手势事件中调用。收银台地址由平台生成，Toy 不能自带 URL；Promise 完成只代表「已拉起」，不代表用户已付款。

参数：
- `minPrice`: number（必填）- 默认选中的档位金额，单位分的正整数，与 getChargeUnlock 同口径

返回值：`Promise<void>`

```js
// 支付结果不由 openChargePanel 返回。用 onChargeUnlockChange 接「付款回来」：
// SDK 自己监听页面重新可见并按上次的 minPrice 重查，结果变了才回调。
const off = toy.onChargeUnlockChange(result => {
  if (result.status === 'ok' && result.data.unlocked) showPaidContent()
})

button.addEventListener('click', async () => {
  await toy.openChargePanel({ minPrice: 1200 })
})
```

### toy.onChargeUnlockChange(listener)

订阅「充电档位鉴权结果发生变化」，返回取消订阅函数。页面重新可见（Web 从收银台标签页切回、App 从收银台页返回）时，SDK 自动按上次 getChargeUnlock 的 minPrice 重查一次，status 变化或 unlocked 翻转才回调。上游查询失败不回调（不把抖动当未解锁）。收到回调请只改 UI、**不要整页刷新**，否则作品内存态（读到第几页）会丢。

参数：
- `listener`: (result: ChargeUnlockResp) => void（必填）- 鉴权结果变化时的回调，参数与 getChargeUnlock 的返回值同构

返回值：`() => void`

```js
// 先查一次（提供门槛金额，也是比较基线）
await toy.getChargeUnlock({ minPrice: 1200 })

const off = toy.onChargeUnlockChange(result => {
  if (result.status === 'ok' && result.data.unlocked) {
    revealPaidChapter() // 原地换 UI，不要 location.reload()
  }
})

// 组件卸载时取消
off()
```

### toy.setCloudStorage(items)

批量写入云存储（upsert），同 key 覆盖旧值。按「登录用户 + Toy」隔离，需用户已登录，但不触发用户数据确认。单个 Toy 最多存储 128 个 key-value。

参数：
- `items`: Record<string, string>（必填）- key/value 键值对。key 只能含字母、数字、下划线和短横线，≤128 字节，且不能以 __ 开头；value 为字符串，≤1024 字节，存对象请自行 JSON.stringify

返回值：`Promise<void>`

```js
await toy.setCloudStorage({ coins: '100', level: '5' })
```

### toy.getCloudStorage(keys?)

读取云存储。不传 keys 读取当前用户在该 toy 下的全部数据；未命中的 key 不出现在结果中。

参数：
- `keys`: string[]（可选）- 要读取的 key 列表，不能以 __ 开头；不传或空数组表示读取全部（平台保留 key 不会返回）

返回值：`Promise<Record<string, string>>`

```js
// 读取指定 key
const { coins } = await toy.getCloudStorage(['coins'])
// 读取全部
const all = await toy.getCloudStorage()
```

### toy.removeCloudStorage(keys)

批量删除云存储中指定的 key。

参数：
- `keys`: string[]（必填）- 要删除的 key 列表，不能以 __ 开头

返回值：`Promise<void>`

```js
await toy.removeCloudStorage(['level'])
```

### toy.setSharedStorage(storageId, items)

批量写入共享存档（upsert），同 key 覆盖旧值。与云存储的区别在隔离维度：云存储按「玩家 + 本 Toy」隔离，共享存档按「玩家 + 存档」隔离——被授权的多个作者名下全部 Toy 读写同一份数据。storageId 在创作中心「共享存档」页创建后复制。作者未被授权时报错 no_permission，存档被创建者删除后报错 not_found，这两类重试无用。

参数：
- `storageId`: string（必填）- 共享存档标识，形如 st_ 加 16 位小写字母数字，在创作中心「共享存档」页创建后复制
- `items`: Record<string, string>（必填）- key/value 键值对，约束与云存储一致：key 只能含字母、数字、下划线和短横线，≤128 字节，且不能以 __ 开头；value 为字符串，≤1024 字节

返回值：`Promise<void>`

```js
await toy.setSharedStorage('st_7f3a9c2e8b1d4g5h', { progress: '42' })
```

### toy.getSharedStorage(storageId, keys?)

读取共享存档。不传 keys 读取当前玩家在该存档下的全部数据；未命中的 key 不出现在结果中。私有云存储的数据不会自动迁移到共享存档。

参数：
- `storageId`: string（必填）- 共享存档标识
- `keys`: string[]（可选）- 要读取的 key 列表；不传或空数组表示读取全部

返回值：`Promise<Record<string, string>>`

```js
// 读取指定 key
const { progress } = await toy.getSharedStorage('st_7f3a9c2e8b1d4g5h', ['progress'])
// 读取全部
const all = await toy.getSharedStorage('st_7f3a9c2e8b1d4g5h')
```

### toy.removeSharedStorage(storageId, keys)

批量删除共享存档中指定的 key。只删当前玩家自己的值，不影响其他玩家；创建者在创作中心删除整个存档才会让所有玩家都取不到。

参数：
- `storageId`: string（必填）- 共享存档标识
- `keys`: string[]（必填）- 要删除的 key 列表

返回值：`Promise<void>`

```js
await toy.removeSharedStorage('st_7f3a9c2e8b1d4g5h', ['progress'])
```

### toy.submitScore(req)

上报分数到排行榜（需用户已登录，首次提交前由平台完成用户数据确认）。按「toy + 榜位 + 周期」隔离。返回我的总榜分数。

参数：
- `board`: number（可选）- 榜位，固定 1 ~ 5，含义由 toy 自定义（如金币榜 / 关卡榜），不传默认 1
- `score`: number（必填）- 本次成绩的绝对分数，不是相对已有成绩的增量。服务端只保留该用户在该榜位的历史最高分：本次 score 高于历史最高才更新，否则保持不变（不会覆盖成更低分）。整数，取值范围 -16777216 ~ 16777215（约 ±1677 万），允许 0 和负数（支撑差值 / 亏损类榜）

返回值：`Promise<{ score: number }>`

```js
// board 不传默认 1；只用单一榜位时可省略
const { score } = await toy.submitScore({ board: 1, score: 100 })
```

### toy.getRankList(req?)

读取榜单（游客可读）。返回前 limit 名，固定从高到低；同分时先达成者靠前（先到先赢），名次唯一、不并列。

参数：
- `board`: number（可选）- 榜位，固定 1 ~ 5，不传默认 1
- `period`: 'all' | 'month' | 'week' | 'day'（可选）- 周期：all（总榜，永久）/ month / week / day，不传按 all
- `limit`: number（可选）- 返回名次数量，不传或超上限按后端默认（≤100）

返回值：`Promise<RankItem[]>（RankItem: { rank, score, nickname, avatar }）`

```js
// board 不传默认 1，只用单一榜位时可省略
const list = await toy.getRankList({ board: 1, period: 'week', limit: 50 })
// list: [{ rank: 1, score: 999, nickname: '张三', avatar: '//p0.hdslb.com/...' }, ...]
```

### toy.getMyRank(req?)

查询我在指定榜单的排名（需用户已登录）。是否上榜必须用 ranked 字段判断，不能用 score（分数允许为 0 / 负）。

参数：
- `board`: number（可选）- 榜位，固定 1 ~ 5，不传默认 1
- `period`: 'all' | 'month' | 'week' | 'day'（可选）- 周期：all / month / week / day，不传按 all

返回值：`Promise<{ ranked: boolean, rank: number, score: number }>（未上榜 ranked=false，rank/score 为 0）`

```js
// board 不传默认 1，period 不传按总榜
const mine = await toy.getMyRank({ board: 1, period: 'week' })
// mine: { ranked: true, rank: 12, score: 88 }
```

### toy.requestCamera(options?)

申请摄像头业务授权和系统权限，并返回浏览器原生 MediaStream；必须由用户手势触发。

参数：
- `options.facingMode`: 'user' | 'environment'（可选）- 前置或后置摄像头，默认 user

返回值：`Promise<MediaStream>`

```js
const stream = await toy.requestCamera({ facingMode: 'environment' })
videoEl.srcObject = stream
// 必须显式 play()：远端流异步到达，已脱离手势上下文，
// iOS 上仅靠 autoplay 不会起播，画面停在黑帧
await videoEl.play().catch(() => {})
```

### toy.requestMicrophone()

申请麦克风业务授权和系统权限，并返回浏览器原生 MediaStream；必须由用户手势触发。

返回值：`Promise<MediaStream>`

```js
const stream = await toy.requestMicrophone()
audioEl.srcObject = stream
await audioEl.play().catch(() => {})
```

### toy.stopMedia(stream)

停止指定媒体流并关闭采集设备；使用完摄像头或麦克风后必须调用。

参数：
- `stream`: MediaStream（必填）- requestCamera 或 requestMicrophone 返回的媒体流

返回值：`Promise<void>`

```js
await toy.stopMedia(stream)
```

### toy.onContainerChange(listener)

监听 Toy 容器状态变化（设备类型、可用尺寸、方向、沉浸状态和安全区），仅 B站 App 内支持。想确认模式是否切换成功：先用本方法监听状态，再调用 setContainerMode()。如果之后收到的状态与你设置的一致，说明切换成功；没有收到变化时，无法确认是否成功。

参数：
- `listener`: (state: ToyContainerState) => void（必填）- 状态通知。开始监听后先收到一次当前完整状态，之后仅在状态变化时收到通知；state.changedFields 标出本次变化的字段

返回值：`() => void`

```js
const off = toy.onContainerChange((state) => {
  stage.style.width = state.viewport.width + 'px'
  stage.style.height = state.viewport.height + 'px'
  stage.style.paddingTop = state.safeArea.top + 'px'

  if (state.changedFields.includes('viewport')) relayoutCanvas()
})

// 页面卸载或不再需要时调用 off() 取消监听
```

### toy.getContainerState()

调用一次即可获取一次当前容器状态；如果希望在状态变化时自动收到通知，再使用 `toy.onContainerChange()`。仅 B站 App 内支持。

返回值：`Promise<ToyContainerState>`

```js
const state = await toy.getContainerState()
console.log(state.deviceType, state.viewport, state.safeArea)
// 主动读取返回的 changedFields 恒为空数组
```

### toy.setContainerMode(req)

原子更新容器方向和沉浸状态，仅 B站 App 内支持；Promise<void> 不代表目标状态已生效。想确认是否切换成功：先用 onContainerChange() 监听状态，再调用本方法。如果之后收到的状态与你设置的一致，说明切换成功；没有收到变化时，无法确认是否成功。

参数：
- `orientation`: 'portrait' | 'landscape' | 'auto'（可选）- 目标方向；auto 表示跟随系统，不传保持当前方向
- `immersive`: boolean（可选）- 是否沉浸显示，不传保持当前状态；方向与沉浸状态需同时变更时请一次传齐，实际结果以当前状态或状态变化为准

返回值：`Promise<void>`

```js
let pendingMode = null

// 先调用 onContainerChange() 监听状态变化，再调用 setContainerMode，避免漏掉状态变化
const off = toy.onContainerChange((state) => {
  const applied = pendingMode &&
    (pendingMode.orientation === undefined || state.orientation === pendingMode.orientation) &&
    (pendingMode.immersive === undefined || state.immersive === pendingMode.immersive)

  if (applied) {
    pendingMode = null
    console.log('目标容器状态已生效', state)
  }
})

async function requestMode(mode) {
  pendingMode = mode
  try {
    await toy.setContainerMode(mode)
    // Promise<void> 只表示调用返回，不是目标状态成功回执；继续等待 onContainerChange
  } catch (error) {
    pendingMode = null
    console.error('setContainerMode 调用失败', error)
  }
}

requestMode({ immersive: true }) // 沉浸模式
// requestMode({ orientation: 'landscape', immersive: true }) // 横屏切换（手机请同时开启沉浸）
// requestMode({ orientation: 'portrait', immersive: false }) // 竖屏切换

// 没有收到匹配的状态变化时（如旧客户端不支持），无法确认是否成功，不能当作成功
// 页面卸载或不再需要时调用 off() 取消监听
```

### toy.onPlayerChange(listener)

监听宿主视频播放器状态（播放位置、总时长、是否播放中、是否静音、播放速率），仅 B站 App 内支持。在起播 / 暂停 / 恢复 / seek / 变速 / 卡顿 / 完播时推送，另有每 10 秒一次心跳；匀速播放期间不推送，不能靠回调频率驱动进度条。position、rate、timestamp 是同一时刻的采样值，实时进度需自行插值：position + (Date.now() - timestamp) * rate。

参数：
- `listener`: (state: ToyPlayerState) => void（必填）- 状态通知。开始监听后先收到一次当前完整状态；state.changedFields 标出本次变化的字段（不含 timestamp），首次推送包含全部字段。position / duration 单位为毫秒，duration 未知时为 0；rate 为实际播放速率，暂停 / 卡顿 / 未就绪时为 0

返回值：`() => void`

```js
const off = toy.onPlayerChange((state) => {
  // 只关心播放 / 静音切换时，按 changedFields 过滤
  if (state.changedFields.includes('playing')) updatePlayButton(state.playing)
  latest = state
})

// 实时进度 = position + (Date.now() - timestamp) * rate
const now = latest.position + (Date.now() - latest.timestamp) * latest.rate

// 页面卸载或不再需要时调用 off() 取消监听
```

### toy.getPlayerState()

调用一次即可获取一次播放器当前完整状态，无需先订阅；如果希望在状态变化时自动收到通知，再使用 toy.onPlayerChange()。仅 B站 App 内支持。

返回值：`Promise<ToyPlayerState>`

```js
const state = await toy.getPlayerState()
console.log(state.position, state.duration, state.playing, state.muted)
// 主动读取返回的 changedFields 恒为空数组
```

### toy.setPlayerState(req)

原子更新播放位置、播放 / 暂停与静音，仅 B站 App 内支持。未传的项保持当前状态，三项都不传会本地抛 invalid_param。多项同时变更必须一次调用，分多次调用会出现可观测的中间状态。

参数：
- `position`: number（可选）- 目标播放位置，单位毫秒，须为非负整数，否则本地抛 invalid_param；超出总时长时由端侧处理
- `playing`: boolean（可选）- true 播放，false 暂停；不传保持当前状态
- `muted`: boolean（可选）- 是否静音；不传保持当前状态

返回值：`Promise<void>`

```js
// 跳到 30 秒处并开始播放：一次下发
await toy.setPlayerState({ position: 30000, playing: true })

// 只切换静音
await toy.setPlayerState({ muted: true })
```

### toy.onPageClose(listener)

监听页面关闭，端侧在销毁 WebView 前发出通知，仅 B站 App 内支持。不保证送达：端侧不等待回执就销毁 WebView，回调可能来不及执行，不能作为唯一的存档时机，需要持久化的数据应在产生时就写入（如 setCloudStorage）。通知是一次性的，关闭后才注册的监听不会补收。

参数：
- `listener`: () => void（必填）- 关闭通知回调，无参数

返回值：`() => void`

```js
const off = toy.onPageClose(() => {
  // 尽力而为的收尾，不要依赖它保存关键数据
  flushPendingLog()
})
```

### toy.checkInputSafety(req)

检测玩家输入的文本是否可以展示（昵称、留言、涂鸦标题等会被其他玩家看到的内容），需用户已登录。无需在平台侧申请权限点，所有 Toy 直接可用。只返回 ok / rejected / unavailable 三态，unavailable 表示检测没跑成，不等于通过。

参数：
- `text`: string（必填）- 待检测文本，非空且 ≤16384 字节（UTF-8，一个汉字算 3 字节），超限本地抛 invalid_param
- `scene`: string（可选）- 业务标记，用于区分昵称 / 留言等入口，不参与判定；字符集仅 [A-Za-z0-9_.:-]、≤64 字节，不能用中文

返回值：`Promise<CheckInputSafetyResp>`

```js
const { passed, status } = await toy.checkInputSafety({
  text: nicknameInput.value,
  scene: 'nickname', // 可选，自己的业务标记，不影响判定
})

if (passed) {
  saveNickname(nicknameInput.value)
} else if (status === 'rejected') {
  tip('这个昵称不能用，换一个试试')
} else {
  // status === 'unavailable'：检测没跑成，不要当作通过
  tip('暂时没法验证，稍后再试')
}
```

## 环境支持

| 方法 | B站 App | Web 端 |
|------|---------|--------|
| isSupport | ✅ | ✅ |
| navigate | ✅ | ✅ |
| saveImageToAlbum | ✅ | ❌ |
| share | ✅ | ❌ |
| getQrCode | ✅ | ✅ |
| sharePicture | ✅ | ❌ |
| closeBrowser | ✅ | ❌ |
| getUserProfile | ✅ | ✅ |
| getAuthorProfile | ✅ | ✅ |
| getAuthorVideos | ✅ | ✅ |
| getAuthorRelation | ✅ | ✅ |
| getVideoUserActions | ✅ | ✅ |
| getAnnualReport | ✅ | ✅ |
| getChargeUnlock | ✅ | ✅ |
| openChargePanel | ✅ | ✅ |
| onChargeUnlockChange | ✅ | ✅ |
| setCloudStorage | ✅ | ✅ |
| getCloudStorage | ✅ | ✅ |
| removeCloudStorage | ✅ | ✅ |
| setSharedStorage | ✅ | ✅ |
| getSharedStorage | ✅ | ✅ |
| removeSharedStorage | ✅ | ✅ |
| submitScore | ✅ | ✅ |
| getRankList | ✅ | ✅ |
| getMyRank | ✅ | ✅ |
| requestCamera | ✅ | ✅ |
| requestMicrophone | ✅ | ✅ |
| stopMedia | ✅ | ✅ |
| onContainerChange | ✅ | ❌ |
| getContainerState | ✅ | ❌ |
| setContainerMode | ✅ | ❌ |
| onPlayerChange | ✅ | ❌ |
| getPlayerState | ✅ | ❌ |
| setPlayerState | ✅ | ❌ |
| onPageClose | ✅ | ❌ |
| checkInputSafety | ✅ | ✅ |

## 注意事项

- Web 端不支持的方法调用后会抛出错误，建议先用 `isSupport` 判断当前环境是否支持再调用。
- 所有错误都带 `[ToySDK]` 前缀，便于排查。
- `navigate` 必须在用户手势事件（如 click）中调用，否则会被拦截。
- `openChargePanel` 同样必须在用户手势事件（如 click）中调用：它要打开新页面，脱离手势上下文会被浏览器拦成弹窗。不要在定时器、网络回调或页面加载时自动调用。
- OpenID 模式启用后，`getUserProfile` 会直接复用未过期的 profile v1/v2 授权；没有有效授权时，首次调用由平台展示“获取你的昵称、头像和当前 Toy 内用户标识”固定数据确认弹窗，Toy 不能自定义弹窗内容，接受后写入 v2 授权并一次返回头像、昵称和 `toyOpenId`。用户资料确认不区分 v1/v2 文案配置；模式关闭时省略 `toyOpenId`。
- `toyOpenId` 是当前登录用户在当前 Toy 内的稳定假名标识，调用方不能指定 UID/MID 或 Toy ID；它不是鉴权凭证，不得写入埋点和公开日志。
- 作者互动关系和视频互动数据只校验登录态，不触发用户数据确认弹窗；只返回业务字段与稳定状态，不返回 UID、MID、登录令牌或用户数据确认挑战值。外部手机浏览器返回 `unsupported` 并引导打开 B站 App。
- 生图类 Toy 保存图片：B站 App 内用 `saveImageToAlbum` 保存到系统相册；Web 端（桌面 / 手机浏览器）该方法不支持，请用标准浏览器下载能力（`<a download>` 或 canvas blob URL，需用户点击触发）。Web 端支持由用户主动点击触发的图片下载，无需额外配置。
- `saveImageToAlbum` 的图片体积：`base64Data` 上限 5MB（5242880），口径是 base64 字符串本身的长度，`data:image/...;base64,` 前缀（可带可不带）和换行等空白字符都计入，不按解码后的原图大小算（base64 比原图大约 4/3，5MB 字符串约对应 3.75M 原图）。超限时直接 reject，错误可按 `error.type === 'invalid_param'` 判定，请用 `try/catch` 处理。另外，即使未超限，字符串越大保存越慢、内存占用也越高，建议把 base64 字符串控制在 2M 以内——这是体验建议，不是会报错的红线。图片更大时优先传 `url`，不受此上限约束。
- 分享（`share`）：仅 B站 App 内支持，Web 端调用会抛错，建议先用 `isSupport('share')` 判断。只传相对当前 Toy 的 `path`，完整分享链接由平台生成，避免分享链接被伪造指向其他 Toy 或外部站点；`path` 越界（绝对 URL、`../` 逃逸）抛 `invalid_param`，页面不在 `/toy/<slug>/` 路径下时抛 `unsupported`。
- 二维码（`getQrCode`）：两个入参都可省略，`toy.getQrCode()` 即当前 Toy 首页的二维码；传了 `path` 则与 `share` 同一约定和同一校验。只能编码当前 Toy 内的页面链接，不能编码任意文本（需要任意字符串二维码请自行在 Toy 内打包二维码库）。App 端和 Web 端都支持，适用于跨设备接力、结算页海报、线下展示等场景。返回完整 PNG data URL，可直接赋给 `img.src`，也可原样作为 `saveImageToAlbum` 的 `base64Data` 传入，不用先去掉 `data:image/png;base64,` 前缀。`size` 为边长像素，区间 [80, 1024] 整数，不传默认 320。
- 云存储（`getCloudStorage` / `setCloudStorage` / `removeCloudStorage`）：需用户已登录，按「登录用户 + Toy」双维度隔离，跟随登录态跨设备持久化，但不触发用户数据确认。value 为字符串，存对象请自行 `JSON.stringify` / `JSON.parse`。写入 / 删除失败时 Promise 会 reject，请用 `try/catch` 处理。
- 云存储容量限制：单个 Toy 最多存储 128 个 key-value；key 只能含字母、数字、下划线和短横线，≤128 字节；value ≤1024 字节。超出均由服务端拦截返回错误。
- 云存储中以 `__` 开头的 key 为平台保留 key，Toy 不能读取、写入或删除。
- 排行榜（`submitScore` / `getRankList` / `getMyRank`）：按「toy + 榜位 board + 周期 period」隔离，跟随登录态跨设备持久化，端内端外均走 HTTP、行为一致。board 固定 1 ~ 5（含义由 toy 自定义），不传默认 1；period 为 all / month / week / day，不传按 all（总榜，永久）。
- 排行榜分数：整数，取值范围 -16777216 ~ 16777215，允许 0 / 负数；排序固定从高到低，同分时先达成者靠前（先到先赢），名次唯一、不并列。
- `submitScore` / `getMyRank` 需用户已登录，`submitScore` 首次提交前由平台完成用户数据确认，`getRankList` 游客可读；`getMyRank` 判断是否上榜必须用 `ranked` 字段，不能用 `score`。失败（未登录、参数非法等）时 Promise 会 reject，请用 `try/catch` 处理。
- 媒体能力已在 B站 App 和 Web 端公开。摄像头与麦克风分别通过 `requestCamera`、`requestMicrophone` 独立申请业务授权和系统权限；前者仅接受 facingMode，后者不接受参数；两者必须由用户手势触发，实际结果仍受系统权限和设备状态影响。
- 使用摄像头或麦克风结束后必须调用 `stopMedia`，确认媒体轨道停止并释放设备。
- 容器状态（`onContainerChange` / `getContainerState` / `setContainerMode`）仅 B站 App 内支持。`onContainerChange` 同步返回取消函数，调用后先收到一次完整状态；`getContainerState` 调用一次即可获取一次当前容器状态，`changedFields` 为空数组。状态包含 `deviceType`（phone / tablet / desktop / unknown）、CSS px 单位的 `viewport` 与 `safeArea`、`orientation`（portrait / landscape）和 `immersive`。
- `setContainerMode` 是方向与沉浸状态的原子更新：未传字段保持当前状态，两个字段都不传会抛 `invalid_param`。`Promise<void>` 不是成功回执，不能据此判断已生效。想确认是否切换成功：先用 `onContainerChange()` 监听状态，再调用 `setContainerMode()`。如果之后收到的状态与你设置的一致，说明切换成功；没有收到变化时，无法确认是否成功（旧客户端可能不会通知状态变化）。`orientation: 'auto'` 表示跟随系统；手机不支持横屏且非沉浸组合。Web 端调用容器能力会抛 `unsupported`。
- 玩家输入内容检测（`checkInputSafety`）：**无需在平台侧申请权限点，所有 Toy 直接可用**，`isSupport('checkInputSafety')` 为 `true` 即可直接调用。只返回 `ok` / `rejected` / `unavailable` 三态，**`unavailable` 表示检测没跑成，不等于通过**，请提示玩家稍后再试，不要放行内容。不返回命中的词、位置、规则与供应商信息，因此无法在 Toy 内标出「哪几个字有问题」。`text` ≤16384 字节（UTF-8，一个汉字 3 字节），`scene` 只是你自己的业务标记、不参与判定且不能用中文（字符集仅 `[A-Za-z0-9_.:-]`）。有调用配额：请在玩家提交内容时检测，不要每次按键都调用，命中限流会抛 `307044` 而不是返回 `unavailable`。App 与 Web 行为一致，只校验登录态，不触发用户数据确认弹窗。
- 年报数据（`getAnnualReport`）：每个观众看到的都是自己的那一份。字段名为 snake_case，与其他能力的驼峰命名不同；`*_video` 与 `hot_arch_list[].video` 的结构与 `getAuthorVideos` 的 `data` 一致，`hot_arch_list[].live` 是直播场次（`title` / `cover` 是直播间**当前**的标题与封面，不是该场开播时的）。值为 `null` 表示该项对当前观众不适用（如年度挚爱 UP 没有直播间互动类指标，年度挚爱主播没有视频类指标），或对应视频已删除、不可见，请按缺省展示。`fans`（粉丝勋章、大航海等级、陪伴天数）是实时数据，不是年度统计值。
- `getAnnualReport` 直接返回年报数据，不带 `status`：部分视频、直播或粉丝关系暂时获取不到时，对应字段为 `null`，其余字段照常可用。失败时 Promise reject，请用 `try/catch` 处理：`error.type` 为 `not_logged_in` 是未登录，`unsupported` 是预览态或外部手机浏览器，`http_error` 是数据暂不可用——**不等于「这个观众没有年报」**，请展示兜底页并提示稍后再来。年报正式上线前返回的是示例数据，只用于制作调试，不要据此对外宣传具体数字。**年报数据将于 2027 年 3 月 31 日下线**，之后调用会 reject（`http_error`），年报类 Toy 需要提前准备下线后的兜底内容（例如「本期年报已结束」），不要让页面空白或报错。
- 充电档位（`getChargeUnlock` / `openChargePanel`）：**需平台侧白名单开通**，未开通时 `getChargeUnlock` 返回 `unsupported`；需 shell 渲染模式，预览态两个能力都不可用（`isSupport` 返回 `false`）。`minPrice` 单位是**分**，12 元要传 `1200`——按元传会把 12 元档当成 0.12 元档，是最容易出的错。
- `getChargeUnlock` 只有 `status === 'ok'` 时才能读 `data.unlocked`。`unavailable` 表示没查成、`unauthorized` 表示未登录、`denied` 表示用户未授权读取互动关系，**三者都不等于「未解锁」也不等于「已解锁」**，请一律按未解锁展示并提示稍后再试，不要放行付费内容。
- `openChargePanel` 的 Promise 完成只代表收银台已拉起，**不是支付成功回执**，也不返回订单信息。支付结果要靠回到 Toy 后重新调 `getChargeUnlock` 确认：端内收银台整页打开、关闭后 Toy 页面重新可见，Web 端在新标签页打开、用户切回本页，两种情况都可以用 `visibilitychange` 触发重新鉴权。
- 鉴权结果不缓存，但也**不要轮询**：在首次展示付费内容前、以及页面重新可见时各查一次即可。接口有调用配额，高频轮询会命中限流。
- Web 端的「App 内限制」：作者可以在发布页勾选「仅允许在哔哩哔哩 App 内打开」。该设置依据浏览器 UA 判定，**是降低绕过风险的措施，不是鉴权边界**，付费内容的真正保护仍在服务端鉴权上。

## 频率限制与最佳实践

云存储、共享存档与排行榜接口按 Toy 限制调用频率：同一个 Toy 的全部玩家共享一份额度，玩家越多越要压低单人请求数。超限后请求会被拒绝并报错 307044「请求过于频繁，请稍后再试」。具体阈值不对外公开且可能调整，按下面几条控制调用节奏即可，正常游玩不会触发。

1. **云存储当作存档，不要当作内存**：游玩中先读写页面内存变量，只在结算、过关、页面隐藏这类关键节点落盘；不要每次得分、每次点击都写。
2. **批量代替循环**：一次 setCloudStorage 带多个键值对、一次 getCloudStorage 带多个 key，不要 for 循环逐 key 调用。
3. **读结果本地缓存，不要轮询**：榜单和存档拉一次后本地复用；确需刷新交给用户手动触发，不要用定时器定期拉。
4. **排行榜按事件提交**：submitScore 只增不减且幂等，结算时提交一次即可；重复提交同分不会覆盖成绩，但一样消耗额度。
5. **失败时退避重试，不要立即重试**：捕获 reject 后先判断是否限流，是则指数退避后重试并给玩家明确提示；立即原样重试会把偶发限流放大成持续限流。

限流时 SDK 会 reject，错误 `type` 为 `http_error`、`code` 为 `307044`，`message` 带服务端文案；云存储与排行榜接口均适用：

```js
try {
  await toy.setCloudStorage({ coins: '100' })
} catch (error) {
  if (error.type === 'http_error' && error.code === 307044) {
    // 触发频率限制：建议指数退避后重试，并给玩家明确提示
  } else {
    // 其他错误（未登录 / 参数非法等），按业务逻辑处理
  }
}
```