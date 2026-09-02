/**
 * Релей вебхуков Продамуса: Продамус -> Cloudflare -> PythonAnywhere.
 *
 * Зачем: прямые запросы Продамуса до PythonAnywhere доходят через раз —
 * TCP-соединение встаёт, а ответа нет (TLS-рукопожатие не завершается по https,
 * ответ не приходит по http). У Cloudflare своя anycast-сеть и другой путь,
 * поэтому нога «Продамус -> Cloudflare» и нога «Cloudflare -> PA» обе рабочие.
 *
 * Тело запроса пересылается байт в байт, вместе с заголовком Sign, иначе
 * подпись HMAC на нашей стороне не сойдётся.
 *
 * Разворачивается через дашборд Cloudflare, см. relay/README.md.
 */

const TARGET = "https://ysingle-goshadvoryak.pythonanywhere.com/prodamus_webhook";

// Заголовки, которые важно донести до приложения без изменений.
const FORWARD_HEADERS = ["sign", "content-type", "content-length", "user-agent"];

export default {
  async fetch(request) {
    if (request.method === "GET") {
      // Проверка живости — из панели Продамуса или руками из браузера.
      return text("Prodamus relay is alive. Send notifications here via POST.", 200);
    }

    if (request.method !== "POST") {
      return text("Method Not Allowed", 405);
    }

    // Настоящий вебхук Продамуса всегда несёт заголовок Sign. Без него не
    // пересылаем: так интернет-сканеры не засоряют лог приложения.
    const sign = request.headers.get("sign");
    if (!sign) {
      return text("Missing Sign header", 400);
    }

    // Именно arrayBuffer, а не text/formData: любое перекодирование тела
    // способно изменить байты, по которым считается подпись.
    const body = await request.arrayBuffer();

    const headers = new Headers();
    for (const name of FORWARD_HEADERS) {
      const value = request.headers.get(name);
      if (value) headers.set(name, value);
    }
    // Чтобы в логе приложения был виден настоящий адрес Продамуса, а не Cloudflare.
    const clientIp = request.headers.get("cf-connecting-ip");
    if (clientIp) headers.set("X-Forwarded-For", clientIp);
    headers.set("X-Relay", "cloudflare-worker");

    try {
      const upstream = await fetch(TARGET, { method: "POST", headers, body });
      // Код и тело возвращаем как есть: Продамус должен увидеть ровно наш ответ,
      // иначе он посчитает доставку неудачной и будет повторять.
      return text(await upstream.text(), upstream.status);
    } catch (e) {
      // 502 -> Продамус повторит попытку позже. Молча терять оплату нельзя.
      return text(`relay error: ${e && e.message ? e.message : e}`, 502);
    }
  },
};

function text(body, status) {
  return new Response(body, {
    status,
    headers: { "content-type": "text/plain; charset=utf-8" },
  });
}
