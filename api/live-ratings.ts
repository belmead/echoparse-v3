import { VercelRequest, VercelResponse } from '@vercel/node';
import axios from 'axios';

// These need to be set in your Vercel server environment.
const APPLE_APP_ID = process.env.APPLE_APP_ID;
const GOOGLE_PACKAGE_ID = process.env.GOOGLE_PACKAGE_ID;

export default async function handler(req: VercelRequest, res: VercelResponse) {
  try {
    // Fetch the live rating from the App Store using Apple’s lookup API
    let appleRating: number | null = null;
    if (APPLE_APP_ID) {
      const appleResp = await axios.get('https://itunes.apple.com/lookup', {
        params: { id: APPLE_APP_ID },
      });
      const result = appleResp.data?.results?.[0];
      if (result && result.averageUserRating) {
        appleRating = result.averageUserRating;
      }
    }

    // Fetch the live rating from Google Play by scraping the app’s page
    let googleRating: number | null = null;
    if (GOOGLE_PACKAGE_ID) {
      const googleResp = await axios.get('https://play.google.com/store/apps/details', {
        params: { id: GOOGLE_PACKAGE_ID, hl: 'en', gl: 'US' },
      });
      const match = googleResp.data.match(/<div[^>]*class="BHMmbe"[^>]*>([0-9.]+)<\\/?div>/);
      if (match) {
        googleRating = parseFloat(match[1]);
      }
    }

    return res.status(200).json({
      success: true,
      data: {
        app_store_live: {
          value: appleRating !== null ? appleRating.toFixed(2) : 'N/A',
          raw_value: appleRating,
          scale: '5',
        },
        play_store_live: {
          value: googleRating !== null ? googleRating.toFixed(2) : 'N/A',
          raw_value: googleRating,
          scale: '5',
        },
      },
    });
  } catch (err: any) {
    return res.status(500).json({
      success: false,
      error: (err as Error).message,
    });
  }
}
