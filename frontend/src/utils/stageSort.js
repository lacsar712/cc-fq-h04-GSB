export function sortStages(stages) {
  return [...(stages || [])].sort((a, b) => (a.stage_order || 0) - (b.stage_order || 0))
}
