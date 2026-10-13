import { int } from '../format'
import type { Interval } from '../types'

const at = (x: number, max: number) => `${(Math.max(0, Math.min(x, max)) / max) * 100}%`

/** ROS ◆ et sa fourchette p10–p90 sur une échelle commune ; `ref` : un repère (ex. la ROS de mon pire joueur). */
export default function RosBar({ ros, max, mark, markLabel }: { ros: Interval; max: number; mark?: number; markLabel?: string }) {
  const label = `ROS ${int(ros.mean)} (${int(ros.p10)}–${int(ros.p90)})${mark != null && markLabel ? `, ${markLabel} ${int(mark)}` : ''}`
  return (
    <div className="rosbar" role="img" aria-label={label} title={label}>
      <span className="rosbar-axis" />
      {mark != null && <span className="rosbar-ref" style={{ left: at(mark, max) }} />}
      <span className="rosbar-interval" style={{ left: at(ros.p10, max), width: `calc(${at(ros.p90, max)} - ${at(ros.p10, max)})` }} />
      <span className="rosbar-mean" style={{ left: at(ros.mean, max) }} />
    </div>
  )
}
