export function sortStages(stages) {
  return [...(stages || [])].sort((a, b) => (b.stage_order || 0) - (a.stage_order || 0))
}
