import type { StatusDistributionItem } from '../../types'

export default function StatusDistribution({
  items,
}: {
  items: StatusDistributionItem[]
}) {
  return (
    <div className="status-list">
      {items.map((item) => (
        <div className="status-row" key={item.estado}>
          <div className="status-label">{item.estado}</div>
          <div className="status-bar">
            <div
              className="status-bar-fill"
              role="progressbar"
              aria-valuenow={Number(item.pct)}
              aria-valuemin={0}
              aria-valuemax={100}
              style={{ width: `${item.pct}%` }}
            />
          </div>
          <div className="status-count">{item.count}</div>
        </div>
      ))}
    </div>
  )
}
