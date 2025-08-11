// api/live-ratings.ts
import { createClient } from '@supabase/supabase-js';
const supabase = createClient(process.env.SUPABASE_URL!, process.env.SUPABASE_SERVICE_KEY!);

export default async function handler(req: any, res: any) {
  const { data: apple, error: appleErr } = await supabase
    .from('app_reviews')
    .select('rating')
    .eq('platform', 'apple');
  const { data: google, error: googleErr } = await supabase
    .from('app_reviews')
    .select('rating')
    .eq('platform', 'google');

  if (appleErr || googleErr) {
    return res.status(500).json({
      success: false,
      error: (appleErr?.message || googleErr?.message),
    });
  }

  const avg = (arr: any[] | null) =>
    arr && arr.length > 0
      ? arr.reduce((acc, row) => acc + Number(row.rating || 0), 0) / arr.length
      : null;

  const avgApple = avg(apple);
  const avgGoogle = avg(google);

  return res.status(200).json({
    success: true,
    data: {
      app_store_live: {
        value: avgApple !== null ? avgApple.toFixed(2) : 'N/A',
        raw_value: avgApple,
        scale: '5',
      },
      play_store_live: {
        value: avgGoogle !== null ? avgGoogle.toFixed(2) : 'N/A',
        raw_value: avgGoogle,
        scale: '5',
      },
    },
  });
}
