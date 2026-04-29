import { getRequestConfig } from "next-intl/server";

const LOCALE = "es-CL" as const;

export default getRequestConfig(async () => {
  const messages = (await import(`../../messages/${LOCALE}.json`)).default;
  return {
    locale: LOCALE,
    messages,
    timeZone: "America/Santiago",
  };
});
