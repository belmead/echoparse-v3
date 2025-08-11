import { createClient } from '@supabase/supabase-js';

// Initialize Supabase client with project URL and service role key.
// These environment variables must be set in Vercel (server-side only).
const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_KEY!
);

export default async function handler(req: any, res: any) {
  try {
    const { data, error } = await supabase
      .from('dashboard_metrics')
      .select('*');

    if (error) {
      return res.status(500).json({ success: false, error: error.message });
    }
    if (!data || data.length === 0) {
      return res.status(200).json({ success: false, data: null });
    }

    // Map database metric names to keys expected by the frontend.
    const metricsMap: Record<string, string> = {
      one_star_percent: 'oneStarPercent',
      avg_sentiment: 'avgSentiment',
      trending_topic: 'trendingTopic',
      volume_delta: 'volumeDelta',
      platform_gap: 'platformGap',
      app_store_rating: 'appStoreRating',
      play_store_rating: 'playStoreRating',
    };

    // Keep only the first (presumably latest) entry per metric_name.
    const latest: Record<string, any> = {};
    for (const row of data) {
      if (!latest[row.metric_name]) {
        latest[row.metric_name] = row;
      }
    }

    // Build the response object.
    const metrics: any = {};
    for (const [name, alias] of Object.entries(metricsMap)) {
      if (latest[name]) {
        metrics[alias] = {
          value: latest[name].metric_value,
          meta: latest[name].metric_meta,
          time_period: latest[name].time_period,
          // Use calculated_at if present; otherwise fall back to metric_meta.calculated_at.
          calculated_at:
            latest[name].calculated_at ??
            (latest[name].metric_meta?.calculated_at ?? null),
        };
      }
    }

    // Derive a last_updated timestamp, if possible.
    let lastUpdated: string | null = null;
    if (data[0]?.metric_meta?.calculated_at) {
      lastUpdated = data[0].metric_meta.calculated_at;
    }

    return res.status(200).json({
      success: true,
      data: metrics,
      last_updated: lastUpdated,
    });
  } catch (err: any) {
    return res.status(500).json({
      success: false,
      error: (err as Error).message,
    });
  }
}
