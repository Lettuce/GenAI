interface QueryProgressBarProps {
  visible: boolean
  stage: 'Analyzing' | 'Searching' | 'Reading' | 'Verifying' | 'Answering' | null
  progress: number
  compact?: boolean
}

const STAGE_ORDER: Array<NonNullable<QueryProgressBarProps['stage']>> = [
  'Analyzing',
  'Searching',
  'Reading',
  'Verifying',
  'Answering',
]

function stageLabel(stage: QueryProgressBarProps['stage']): string {
  if (!stage) {
    return 'Preparing'
  }
  return stage
}

export function QueryProgressBar({ visible, stage, progress, compact = false }: QueryProgressBarProps) {
  if (!visible) {
    return null
  }

  const normalizedProgress = Math.max(5, Math.min(100, Math.round(progress)))
  const currentIndex = stage ? STAGE_ORDER.indexOf(stage) : -1

  return (
    <div className={compact ? 'rounded-lg border border-slate-200 bg-white px-3 py-2' : 'border-t border-slate-200 bg-white px-4 py-3'}>
      <div className="mb-2 flex items-center justify-between">
        <p className="text-xs font-medium text-slate-700">Query progress: {stageLabel(stage)}</p>
        <p className="text-xs text-slate-500">{normalizedProgress}%</p>
      </div>

      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
        <div
          className="h-full rounded-full bg-slate-900 transition-all duration-300 ease-out"
          style={{ width: `${normalizedProgress}%` }}
        />
      </div>

      <div className="mt-2 grid grid-cols-5 gap-1 text-[11px] text-slate-500">
        {STAGE_ORDER.map((item, index) => {
          const reached = currentIndex >= index
          return (
            <span key={item} className={reached ? 'font-medium text-slate-700' : ''}>
              {item}
            </span>
          )
        })}
      </div>
    </div>
  )
}
