import { useEffect, useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { fetchHistory, type Sample } from '../api';
import { formatTops } from '../format';

export function RateChart({ workerId }: { workerId: string }) {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    const load = async (): Promise<void> => {
      try {
        const data = await fetchHistory(workerId, 60);
        if (active) {
          setSamples(data);
          setFailed(false);
        }
      } catch {
        if (active) {
          setFailed(true);
        }
      }
    };
    void load();
    const timer = setInterval(() => void load(), 10_000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [workerId]);

  if (failed) {
    return <p className="muted">History unavailable.</p>;
  }
  if (samples.length === 0) {
    return <p className="muted">Collecting data… (history appears after a few heartbeats)</p>;
  }

  const data = samples.map((sample) => ({
    time: new Date(sample.ts).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    }),
    tops: sample.tops,
  }));

  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#22303a" />
          <XAxis dataKey="time" stroke="#7e8c93" fontSize={11} minTickGap={32} />
          <YAxis
            stroke="#7e8c93"
            fontSize={11}
            width={84}
            tickFormatter={(value: number) => formatTops(value)}
          />
          <Tooltip
            formatter={(value: number) => formatTops(value)}
            contentStyle={{
              background: '#131a20',
              border: '1px solid #28333d',
              borderRadius: 8,
              color: '#e9f2f3',
            }}
          />
          <Line
            type="monotone"
            dataKey="tops"
            stroke="#34d3c2"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
