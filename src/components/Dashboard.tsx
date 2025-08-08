import React, { useState, useEffect, useRef } from 'react';
import LLMSection from './LLMSection';

// Types for our API data
interface MetricData {
  value: string;
  raw_value: number | string;
  scale?: string;
  source?: string;
}

interface DashboardMetrics {
  one_star_reviews?: MetricData;
  avg_sentiment?: MetricData;
  trending_topic?: MetricData;
  review_volume_delta?: MetricData;
  platform_score_gap?: MetricData;
  app_store_rating?: MetricData;
  play_store_rating?: MetricData;
}

interface LiveRatings {
  app_store_live?: MetricData;
  play_store_live?: MetricData;
}

interface ApiResponse<T> {
  success: boolean;
  data: T;
  last_updated?: string;
  timestamp?: string;
}

// Reusable Card Component
const Card: React.FC<{
  title: string;
  value: string;
  subtitle?: string;
  className?: string;
  onClick?: () => void;
}> = ({ title, value, subtitle, className = "", onClick }) => (
  <div
    className={`bg-zinc-800 opacity-90 rounded-lg p-6 text-white transition-transform duration-200 ease-in-out hover:scale-105 ${className} cursor-pointer`}
    onClick={onClick}
  >
    <div className="text-sm text-gray-400 mb-2 font-mono">{title}</div>
    <div className="text-3xl font-bold mb-1">{value}</div>
    {subtitle && <div className="text-sm text-gray-400">{subtitle}</div>}
  </div>
);

// Main Dashboard Component
const Dashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<DashboardMetrics>({});
  const [liveRatings, setLiveRatings] = useState<LiveRatings>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const llmSectionRef = useRef<any>(null);

  const fetchMetrics = async () => {
    try {
      const response = await fetch('http://localhost:8000/metrics');
      const result: ApiResponse<DashboardMetrics> = await response.json();
      
      if (result.success) {
        setMetrics(result.data);
        setLastUpdated(result.last_updated || null);
      } else {
        setError('Failed to fetch metrics');
      }
    } catch (err) {
      setError('Error connecting to API');
      console.error('Metrics fetch error:', err);
    }
  };

  const fetchLiveRatings = async () => {
    try {
      const response = await fetch('http://localhost:8000/live-ratings');
      const result: ApiResponse<LiveRatings> = await response.json();
      
      if (result.success) {
        setLiveRatings(result.data);
      }
    } catch (err) {
      console.error('Live ratings fetch error:', err);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchMetrics(), fetchLiveRatings()]);
      setLoading(false);
    };

    loadData();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-white text-xl">Loading dashboard...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-red-400 text-xl">Error: {error}</div>
      </div>
    );
  }

  // Helper to send a prompt to LLMSection
  const handleCardPrompt = (title: string) => {
    if (llmSectionRef.current && llmSectionRef.current.submitPrompt) {
      llmSectionRef.current.submitPrompt(`What is the '${title}'?`);
    }
  };

  return (
    <div className="min-h-screen p-8 relative overflow-hidden">
      {/* Scrim overlay */}
      <div className="fixed inset-0 bg-black/70 z-0 pointer-events-none" />
      {/* Header */}
      <div className="flex justify-between items-center mb-8 w-full relative z-10">
        <h1 className="text-4xl font-light text-white font-mono">echoparse▁v3</h1>
        <div className="text-white font-mono">Logout</div>
      </div>

      {/* Dashboard Grid */}
      <div className="w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8 relative z-10">
        
        {/* Row 1: App Store Ratings */}
        <Card
          title="Live App Store Rating"
          value={liveRatings.app_store_live?.value || "unk"}
          onClick={() => handleCardPrompt('Live App Store Rating')}
        />
        
        <Card
          title="App Store Rating (30d)"
          value={metrics.app_store_rating?.value || "unk"}
          onClick={() => handleCardPrompt('App Store Rating (30d)')}
        />
        
        <Card
          title="Live Play Store Rating"
          value={liveRatings.play_store_live?.value || "unk"}
          onClick={() => handleCardPrompt('Live Play Store Rating')}
        />
        
        <Card
          title="Play Store Rating (30d)"
          value={metrics.play_store_rating?.value || "unk"}
          onClick={() => handleCardPrompt('Play Store Rating (30d)')}
        />

        {/* Row 2: Key Metrics */}
        <Card
          title="1-Star Reviews (30d)"
          value={metrics.one_star_reviews?.value || "unk"}
          onClick={() => handleCardPrompt('1-Star Reviews (30d)')}
        />
        
        <Card
          title="Avg. Sentiment (30d)"
          value={metrics.avg_sentiment?.value || "unk"}
          onClick={() => handleCardPrompt('Avg. Sentiment (30d)')}
        />
        
        <Card
          title="Trending Topic"
          value={metrics.trending_topic?.value || "N/A"}
          onClick={() => handleCardPrompt('Trending Topic')}
        />

        {/* Row 2: Volume & Comparison */}
        <Card
          title="Review Vol. Change"
          value={metrics.review_volume_delta?.value || "0%"}
          className={
            metrics.review_volume_delta?.raw_value &&
            typeof metrics.review_volume_delta.raw_value === 'number' &&
            metrics.review_volume_delta.raw_value > 0
              ? "border-l-4 border-green-500"
              : "border-l-4 border-red-500"
          }
          onClick={() => handleCardPrompt('Review Vol. Change')}
        />

      </div>

      {/* Status Indicators */}
      <div className="relative z-10">
        <LLMSection ref={llmSectionRef} lastUpdated={lastUpdated || undefined} embeddingModel="A1DVDTAOAI01-text-embedding-3-small" />
      </div>
    </div>
  );
};

export default Dashboard;