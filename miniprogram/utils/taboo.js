// 家属填的忌讳常常是整句（demo 数据就是"不要提去世的老伴"），
// 所以匹配前先剥掉这些噪声词和"的/了"，剩下的才是真正的关键词。
const TABOO_NOISE = [
  '不要提', '别提', '不想提', '不要说', '别说', '不能提', '不要', '不想',
  '去世', '过世', '走了', '死的', '过身',
];

function normalizeTaboo(text) {
  let s = (text || '').trim();
  TABOO_NOISE.forEach((w) => {
    s = s.split(w).join('');
  });
  return s.replace(/[的了]/g, '').trim();
}

function shouldHidePhrase(phrase, taboos) {
  const np = normalizeTaboo(phrase);
  return (taboos || []).some((t) => {
    if (!t) return false;
    if (phrase.indexOf(t) >= 0) return true;
    const nt = normalizeTaboo(t);
    if (!nt) return false;
    if (np.indexOf(nt) >= 0 || nt.indexOf(np) >= 0) return true;
    return nt.split(/[^\u4e00-\u9fa5a-zA-Z0-9]+/).some((k) => k.length >= 2 && np.indexOf(k) >= 0);
  });
}

module.exports = { TABOO_NOISE, normalizeTaboo, shouldHidePhrase };
