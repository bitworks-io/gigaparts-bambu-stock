import { createApp, type Env } from "./app";

const app = createApp();

export default {
  fetch(request: Request, env: Env) {
    return app.fetch(request, env);
  }
};
