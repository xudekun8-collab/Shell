# 语音合成（TTS）接入说明

当前 `/api/tts` 只搭了骨架，不接真实云服务：

- `TTS_API_KEY` 为空 → 返回 503「语音合成服务未配置」。
- `TTS_API_KEY` 非空 → 返回 501「语音合成尚未接入，见 docs/tts.md」。

## 接入点

在 `backend/app/api/tts.py` 的 `synthesize` 函数里接入云 TTS：

1. 用 `config.TTS_PROVIDER` 决定走哪家服务（azure / aliyun / tencent）。
2. 用 `config.TTS_API_KEY` 鉴权、`config.TTS_VOICE` 选音色。
3. 拿到 mp3 字节流后返回 `StreamingResponse(content=bytes, media_type="audio/mpeg")`。
4. 不得在日志或错误响应里打印 `TTS_API_KEY` 或 text 原文。

## 注意

本机 pip 无网络，装不了 edge-tts / azure / 讯飞等新依赖，所以本轮不引入任何新包。音频不落库，只做「文字 → 音频」的合成，与语音识别（ASR，微信同声传译插件）是两回事。
