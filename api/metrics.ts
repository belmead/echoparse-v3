// api/metrics.ts
import { createClient } from '@supabase/supabase-js';
const supabase = createClient(process.env.SUPABASE_URL!, process.env.SUPABASE_SERVICE_KEY!);

export default async function handler(req: any, res: any) {
  const { data, error } = await supabase
    .from('metrics_daily')
    .select('*')
    .order('date', { ascending: false })
    .limit(1);

  if (error) {
    return res.status(500).json({ success: false, error: error.message });
  }
  if (!data || data.length === 0) {
    return res.status(200).json({ success: false, data: null });
  }
  const row = data[0];
  return res.status(200).json({
    success: true,
    data: row,
    last_updated: row.date,
  });
}
