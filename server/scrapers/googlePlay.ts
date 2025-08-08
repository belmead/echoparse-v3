import gplay from 'google-play-scraper';

export async function getLiveGooglePlayRating(
  appId: string = 'com.ifs.banking.fiid1454'
): Promise<number|null> {
  try {
    const result = await gplay.app({ appId, lang: 'en', country: 'us' });
    return typeof result.score === 'number' ? result.score : null;
  } catch (err) {
    console.error('Error fetching Google Play rating:', err);
    return null;
  }
}
