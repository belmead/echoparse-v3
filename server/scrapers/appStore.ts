import axios from 'axios';

export async function getLiveAppStoreRating(
  appId: number = 677420559
): Promise<number|null> {
  try {
    const { data } = await axios.get(
      `https://itunes.apple.com/lookup?id=${appId}`
    );
    const rating = data?.results?.[0]?.averageUserRating;
    return typeof rating === 'number' ? rating : null;
  } catch (err) {
    console.error('Error fetching Apple rating:', err);
    return null;
  }
}
