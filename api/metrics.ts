import { createClient } from '@supabase/supabase-js';

// Initialize Supabase client with project URL and service role key.
// These environment variables must be set in Vercel (server-side only) to
// point to the same Supabase project used by the data ingestion pipeline.
const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_KEY!
);

export default async function handler(req: any, res: any) {
  try {
    // Fetch the most recent entries from the dashboard_metrics table.  We order
    // by calculated_at descending so the first occurrence of each metric_name
    // represents the latest metric.
    const { data, error } = await supabase
      .from('dashboard_metrics')
      .select('*')
      .order('calculated_at', { ascending: false });

    if (error) {
      return res.status(500).json({ success: false, error: error.message });
    }
    if (!data || data.length === 0) {
      return res.status(200).json({ success: false, data: null });
    }

    // Map database metric names to the keys expected by the frontend.
    const metricsMap: Record<string, string> = {
      one_star_percent: 'oneStarPercent',
      avg_sentiment: 'avgSentiment',
      trending_topic: 'trendingTopic',
      volume_delta: 'volumeDelta',
      platform_gap: 'platformGap',
      app_store_rating: 'appStoreRating',
      play_store_rating: 'playStoreRating',
    };

    // Keep only the latest row per metric_name.
    const latest: Record<string, any> = {};
    for (const row of data) {
      if (!latest[row.metric_name]) {
      latest[row.metric_name] = row;
      }
    }

    // Build the response object. Each metric becomes a property with
    // additional metadata (time_period, calculated_at) preserved from the DB.
    const metrics: any = {};
    for (const [name, alias] of Object.entries(metricsMap)) {
      if (latest[name]) {
        metrics[alias] = {
          value: latest[name].metric_value,
          meta: latest[name].metric_meta,
          time_period: latest[name].time_period,
          calculated_at: latest[name].calculated_at,
        };
      }
    }

    // Use the timestamp of the first row as a reasonable approximation of the
    // last update time.
    const lastUpdated = data[0].calculated_at || null;
    return res.status(200).json({
      success: true,
      data: metrics,
      last_updated: lastUpdated,
    });
  } catch (err) {
    return res.status(500).json({
      success: false,
      error: (err as Error).message,
    });
  }
}
