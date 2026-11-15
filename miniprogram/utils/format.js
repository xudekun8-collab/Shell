// 纯函数集中放这里：不依赖 wx / getApp，可以在 node 里直接 require 做单元测试。
// 页面里只调用，不再各自复制一份实现。

// 模型回复的前端兜底：空回复给固定话术，超长按句号截断，避免一屏糊满
function normalizeReply(text) {
  const s = (text || '').trim();
  if (!s) return '我这儿没听清，您再说一遍';
  if (s.length <= 300) return s;
  const head = s.slice(0, 300);
  const cut = Math.max(
    head.lastIndexOf('。'),
    head.lastIndexOf('？'),
    head.lastIndexOf('！'),
    head.lastIndexOf('?'),
    head.lastIndexOf('!'),
    head.lastIndexOf('.')
  );
  return cut > 150 ? s.slice(0, cut + 1) : head;
}

function pad2(value) {
  return ('0' + value).slice(-2);
}

// 训练用时：老人对「秒」和「分」更敏感，不做小时进位
function formatDuration(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds || 0));
  if (s < 60) return s + ' 秒';
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m + ' 分 ' + r + ' 秒';
}

// 老人看日期更认「今天 / 昨天」，其余 7 天内说「N 天前」，再往前用 月-日
function dateLabel(dateStr, today) {
  if (!dateStr) return '';
  const parts = String(dateStr).split('-');
  if (parts.length < 3) return dateStr;
  const target = new Date(
    parseInt(parts[0], 10),
    parseInt(parts[1], 10) - 1,
    parseInt(parts[2], 10)
  );
  const now = today || new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const diffDays = Math.round((todayStart.getTime() - target.getTime()) / 86400000);
  if (diffDays === 0) return '今天';
  if (diffDays === 1) return '昨天';
  if (diffDays > 1 && diffDays < 7) return diffDays + ' 天前';
  return target.getMonth() + 1 + '-' + pad2(target.getDate());
}

// 列表 wx:key 用的稳定键：后端记录没有主键，用「时间 + 类型 + 序号」拼出来
function listKey(item, index) {
  const createdAt = (item && item.created_at) || '';
  const type = (item && (item.game_type || item.type)) || '';
  return createdAt + '|' + type + '|' + index;
}

module.exports = { normalizeReply, formatDuration, dateLabel, listKey };
