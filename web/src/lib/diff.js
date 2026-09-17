// 简易行级 diff：返回 [{tag: 'same'|'add'|'del', text}]
export function diffLines(oldText, newText) {
  const a = (oldText || '').split('\n')
  const b = (newText || '').split('\n')
  // 最长公共子序列（朴素，文本规模小足够）
  const n = a.length
  const m = b.length
  const dp = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
  const out = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      out.push({ tag: 'same', text: a[i] })
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ tag: 'del', text: a[i++] })
    } else {
      out.push({ tag: 'add', text: b[j++] })
    }
  }
  while (i < n) out.push({ tag: 'del', text: a[i++] })
  while (j < m) out.push({ tag: 'add', text: b[j++] })
  return out
}
