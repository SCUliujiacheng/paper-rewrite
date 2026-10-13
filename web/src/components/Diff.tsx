export function Diff({ original, output, label }: { original: string; output: string; label: string }) {
  // Linear prefix/suffix comparison stays responsive for full-length drafts.
  const left = Array.from(original), right = Array.from(output);
  let start = 0, end = 0;
  while (start < left.length && start < right.length && left[start] === right[start]) start++;
  while (end < left.length - start && end < right.length - start && left[left.length - 1 - end] === right[right.length - 1 - end]) end++;
  return <div className="diff" aria-label={label}><span>{right.slice(0, start).join('')}</span>{left.length - start - end > 0 && <del>{left.slice(start, left.length - end).join('')}</del>}{right.length - start - end > 0 && <ins>{right.slice(start, right.length - end).join('')}</ins>}<span>{end ? right.slice(right.length - end).join('') : ''}</span></div>;
}
