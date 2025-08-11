// api/metrics.ts
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_KEY!
);

export default async function handler(req: any, res: any) {
  const { data, error } = await supabase
    .from('metrics_daily')
    .select('*')
    .order('date', { ascending: false })
    .limit(1);

  if (error) {
    return res.status(500).json({ error: error.message });
  }
  return res.status(200).json(data?.[0] ?? {});
}
