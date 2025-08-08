import { getLiveAppStoreRating } from '../server/scrapers/appStore.js';
import { getLiveGooglePlayRating } from '../server/scrapers/googlePlay.js';

export default async function handler(req, res) {
  console.log('[live-scores] invoked');
  try {
    const [ios, android] = await Promise.all([
      getLiveAppStoreRating(),
      getLiveGooglePlayRating(),
    ]);
    console.log('[live-scores] success:', { ios, android });
    res.status(200).json({ ios, android });
  } catch (err) {
    console.error('[live-scores] error:', err);
    res.status(500).json({ error: err.message, stack: err.stack });
  }
}
