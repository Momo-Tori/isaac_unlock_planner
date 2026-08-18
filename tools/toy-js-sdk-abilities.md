# Toy JS SDK 能力清单

> 版本：1.6.0 ｜ 更新时间：2026-08-12

Toy JS SDK 为你的 Toy 页面提供与 B站 App / Web 环境交互的能力。

> ⚠️ **数据使用限制**：SDK 仅在用户确认后向 Toy 页面返回 getUserProfile 约定的头像、昵称和当前 Toy 内用户标识；不会向 Toy 提供 UID/MID、登录令牌、确认挑战值或可用于跨 Toy 识别的真实账号信息。其他能力仅返回各自文档约定的业务字段。

## 接入方式

在 HTML 的 `<head>` 中添加：

```html
<script src="//s1.hdslb.com/bfs/seed/toy/app/sdk/toy-sdk.js"></script>
```

加载后全局可用 `window.toy` 对象，所有方法返回 Promise。用户与作者数据、云存储和排行榜在 B站 App/Web 行为一致；保存图片、关闭页面、拉起分享等能力仅在 B站 App 内可用，调用前建议先用 `isSupport` 判断。

## 能力列表

### toy.isSupport(ability)

判断当前环境是否支持指定能力。

参数：
- `ability`: string（必填）- 能力名称：navigate | saveImageToAlbum | share | getQrCode | closeBrowser | getUserProfile | getCloudStorage | setCloudStorage | removeCloudStorage | getAuthorProfile | getAuthorVideos | getAuthorRelation | getVideoUserActions | submitScore | getRankList | getMyRank | requestCamera | requestMicrophone | stopMedia

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
- `aids`: number[]（必填）- 1–50 个正整数 aid；SDK 去重并保留首次出现顺序

返回值：`Promise<VideoUserActionsResp>`

```js
const result = await toy.getVideoUserActions({ aids: [170001, 455017605] })
result.items.forEach(item => {
  if (item.status === 'ok') console.log(item.liked, item.coinCount, item.favorited)
})
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

### toy.submitScore(req)

上报分数到排行榜（需用户已登录，首次提交前由平台完成用户数据确认）。按「toy + 榜位 + 周期」隔离。返回我的总榜分数。

参数：
- `board`: number（可选）- 榜位，固定 1 / 2 / 3，含义由 toy 自定义（如金币榜 / 关卡榜），不传默认 1
- `score`: number（必填）- 本次成绩的绝对分数，不是相对已有成绩的增量。服务端只保留该用户在该榜位的历史最高分：本次 score 高于历史最高才更新，否则保持不变（不会覆盖成更低分）。整数，取值范围 -16777216 ~ 16777215（约 ±1677 万），允许 0 和负数（支撑差值 / 亏损类榜）

返回值：`Promise<{ score: number }>`

```js
// board 不传默认 1；只用单一榜位时可省略
const { score } = await toy.submitScore({ board: 1, score: 100 })
```

### toy.getRankList(req?)

读取榜单（游客可读）。返回前 limit 名，固定从高到低；同分时先达成者靠前（先到先赢），名次唯一、不并列。

参数：
- `board`: number（可选）- 榜位，固定 1 / 2 / 3，不传默认 1
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
- `board`: number（可选）- 榜位，固定 1 / 2 / 3，不传默认 1
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
```

### toy.requestMicrophone()

申请麦克风业务授权和系统权限，并返回浏览器原生 MediaStream；必须由用户手势触发。

返回值：`Promise<MediaStream>`

```js
const stream = await toy.requestMicrophone()
audioEl.srcObject = stream
```

### toy.stopMedia(stream)

停止指定媒体流并关闭采集设备；使用完摄像头或麦克风后必须调用。

参数：
- `stream`: MediaStream（必填）- requestCamera 或 requestMicrophone 返回的媒体流

返回值：`Promise<void>`

```js
await toy.stopMedia(stream)
```

## 环境支持

| 方法 | B站 App | Web 端 |
|------|---------|--------|
| isSupport | ✅ | ✅ |
| navigate | ✅ | ✅ |
| saveImageToAlbum | ✅ | ❌ |
| share | ✅ | ❌ |
| getQrCode | ✅ | ✅ |
| closeBrowser | ✅ | ❌ |
| getUserProfile | ✅ | ✅ |
| getAuthorProfile | ✅ | ✅ |
| getAuthorVideos | ✅ | ✅ |
| getAuthorRelation | ✅ | ✅ |
| getVideoUserActions | ✅ | ✅ |
| setCloudStorage | ✅ | ✅ |
| getCloudStorage | ✅ | ✅ |
| removeCloudStorage | ✅ | ✅ |
| submitScore | ✅ | ✅ |
| getRankList | ✅ | ✅ |
| getMyRank | ✅ | ✅ |
| requestCamera | ✅ | ✅ |
| requestMicrophone | ✅ | ✅ |
| stopMedia | ✅ | ✅ |

## 注意事项

- Web 端不支持的方法调用后会抛出错误，建议先用 `isSupport` 判断当前环境是否支持再调用。
- 所有错误都带 `[ToySDK]` 前缀，便于排查。
- `navigate` 必须在用户手势事件（如 click）中调用，否则会被拦截。
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
- 排行榜（`submitScore` / `getRankList` / `getMyRank`）：按「toy + 榜位 board + 周期 period」隔离，跟随登录态跨设备持久化，端内端外均走 HTTP、行为一致。board 固定 1 / 2 / 3（含义由 toy 自定义），不传默认 1；period 为 all / month / week / day，不传按 all（总榜，永久）。
- 排行榜分数：整数，取值范围 -16777216 ~ 16777215，允许 0 / 负数；排序固定从高到低，同分时先达成者靠前（先到先赢），名次唯一、不并列。
- `submitScore` / `getMyRank` 需用户已登录，`submitScore` 首次提交前由平台完成用户数据确认，`getRankList` 游客可读；`getMyRank` 判断是否上榜必须用 `ranked` 字段，不能用 `score`。失败（未登录、参数非法等）时 Promise 会 reject，请用 `try/catch` 处理。
- 媒体能力已在 B站 App 和 Web 端公开。摄像头与麦克风分别通过 `requestCamera`、`requestMicrophone` 独立申请业务授权和系统权限；前者仅接受 facingMode，后者不接受参数；两者必须由用户手势触发，实际结果仍受系统权限和设备状态影响。
- 使用摄像头或麦克风结束后必须调用 `stopMedia`，确认媒体轨道停止并释放设备。
