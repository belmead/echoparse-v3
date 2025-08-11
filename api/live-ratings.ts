import { VercelRequest, VercelResponse } from '@vercel/node';
import axios from 'axios';

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
      if (result && result.averageUserRating) {
        appleRating = result.averageUserRating;
      }
    } catch {
      // ignore Apple errors
    }
  }

  // Google rating via scraping the Play store page
  if (GOOGLE_PACKAGE_ID) {
    try {
      const resp = await axios.get('https://play.google.com/store/apps/details', {
        params: { id: GOOGLE_PACKAGE_ID, hl: 'en', gl: 'US' },
      });
      // Look for "<number> star" in the raw HTML
      const match = resp.data.match(/([0-9.]+)\s*star/);
      if (match) {
        googleRating = parseFloat(match[1]);
      }
    } catch {
      // ignore Google errors
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
}
