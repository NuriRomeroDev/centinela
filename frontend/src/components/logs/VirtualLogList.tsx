import { VirtualScroller } from 'primereact/virtualscroller'
import LogRow from './LogRow'
import type { LogEntry } from '../../types'

interface VirtualLogListProps {
  items: LogEntry[]
  onSelect: (id: number) => void
}

export default function VirtualLogList({ items, onSelect }: VirtualLogListProps) {
  return (
    <div className="virtual-list">
      <VirtualScroller
        items={items}
        itemSize={56}
        numToleratedItems={4}
        style={{ height: 480 }}
        itemTemplate={(log: LogEntry, options: { index: number }) => (
          <LogRow log={log} index={options.index} onSelect={onSelect} />
        )}
      />
    </div>
  )
}
