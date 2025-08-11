import { VercelRequest, VercelResponse } from '@vercel/node';
import axios from 'axios';

// These need to be set in your Vercel server environment.
const APPLE_APP_ID = process.env.APPLE_APP_ID;
const GOOGLE_PACKAGE_ID = process.env.GOOGLE_PACKAGE_ID;

export default async function handler(req: VercelRequest, res: VercelResponse) {
  let appleRating: number | null = null;
  let googleRating: number | null = null;

  // Apple rating via iTunes lookup API
  if (APPLE_APP_ID) {
    try {
      const appleResp = await axios.get('https://itunes.apple.com/lookup', {
        params: { id: APPLE_APP_ID },
      });
      const result = appleResp.data?.results?.[0];
      if (result && typeof result.averageUserRating === 'number') {
        appleRating = result.averageUserRating;
      }
    } catch {
      // ignore Apple errors – we'll fall back to null
    }
  }

  // Google rating via scraping the Play store page
  if (GOOGLE_PACKAGE_ID) {
    try {
      const resp = await axios.get('https://play.google.com/store/apps/details', {
        params: { id: GOOGLE_PACKAGE_ID, hl: 'en', gl: 'US' },
      });
      // Look for "<number> star" (e.g. "4.7 star") in the raw HTML
      const match = resp.data.match(/([0-9]+(?:\.[0-9]+)?)\s*star/);
      if (match) {
        const parsed = parseFloat(match[1]);
        // Only assign if parsed is a finite number
        if (Number.isFinite(parsed)) {
          googleRating = parsed;
        }
      }
    } catch {
      // ignore Google errors – we'll fall back to null
    }
  }

  // Ensure we never return NaN: treat non-finite numbers as null
  const validApple: number | null =
    Number.isFinite(appleRating) ? (appleRating as number) : null;
  const validGoogle: number | null =
    Number.isFinite(googleRating) ? (googleRating as number) : null;

  return res.status(200).json({
    success: true,
    data: {
      app_store_live: {
        value: validApple !== null ? validApple.toFixed(2) : 'N/A',
        raw_value: validApple,
        scale: '5',
      },
      play_store_live: {
        value: validGoogle !== null ? validGoogle.toFixed(2) : 'N/A',
        raw_value: validGoogle,
        scale: '5',
      },
    },
  });
}
