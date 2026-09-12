import { createMockServices } from "./mock-services";
import { devicePlayback } from "./device-playback";

// Single composition point. Inject an HTTP/streaming implementation here later.
export const services = createMockServices(devicePlayback);
