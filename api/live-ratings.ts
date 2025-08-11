// api/live-ratings.ts
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_KEY!
);

export default async function handler(req: any, res: any) {
  const { data, error } = await supabase
    .from('app_reviews')
    .select('rating');

  if (error) {
    return res.status(500).json({ error: error.message });
  }
  if (!data || data.length === 0) {
    return res.status(200).json({ average: null });
  }

  const sum = data.reduce((acc, row) => acc + Number(row.rating || 0), 0);
  const avg = sum / data.length;
  return res.status(200).json({ average: avg });
}
