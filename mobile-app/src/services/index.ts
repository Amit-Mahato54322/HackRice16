import { createHttpServices } from "./http-services";
import { devicePlayback } from "./device-playback";

// Single composition point. Every figure the app shows comes from the backend;
// there is no scripted fallback, so a backend that is down surfaces as an
// error rather than as plausible-looking invented data.
export const services = createHttpServices(devicePlayback);
