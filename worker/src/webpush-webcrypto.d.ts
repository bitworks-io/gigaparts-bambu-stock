declare module "webpush-webcrypto" {
  export class ApplicationServerKeys {
    static generate(): Promise<ApplicationServerKeys>;
    static fromJSON(keys: { publicKey: string; privateKey: string }): Promise<ApplicationServerKeys>;
    toJSON(): Promise<{ publicKey: string; privateKey: string }>;
  }

  export function generatePushHTTPRequest(options: {
    applicationServerKeys: ApplicationServerKeys;
    payload: string;
    target: {
      endpoint: string;
      keys: {
        p256dh: string;
        auth: string;
      };
    };
    adminContact: string;
    ttl: number;
    urgency: "very-low" | "low" | "normal" | "high";
  }): Promise<{ endpoint: string; headers: HeadersInit; body: ArrayBuffer }>;
}
