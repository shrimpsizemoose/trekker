-- Lab 01: HTTP service check
-- This Lua config compiles to a Go checker binary

lab = {
    id = "01",
    name = "Web Service Lab",
    env_prefix = "NPL",
}

required_env = {
    { name = "STUDENT",           error = "Мне надо знать, как тебя зовут ващемпто" },
    { name = "TOKEN",             error = "Мне нужен токен, чтобы убедиться что ты это ты" },
    { name = "COHORT",            error = "Мне надо также знать, из какой ты когорты (задай NPL_COHORT)" },
    { name = "LAB01_EXTERNAL_IP", error = "Если нет айпишника, то я не знаю, куда мне постучаться" },
}

optional_env = {
    { name = "LAB01_WEB_PORT", default = "8000", message = "использую порт по умолчанию" },
}

usage_text = [[
🤌 Чекер конфигурируется через переменные окружения

{{.EnvPrefix}}_LAB01_EXTERNAL_IP - внешний адрес вашей машины
{{.EnvPrefix}}_LAB01_WEB_PORT - порт, по которому будет работать вебсервер (если не задать, то будет 8000)
{{.EnvPrefix}}_STUDENT - ваше имя, как логин в ЛК (например herbie.hancock)
{{.EnvPrefix}}_COHORT - ваша когорта, например, DE99 (большими буквами)
{{.EnvPrefix}}_TOKEN - ваш секретный токен, например, sk-npl-Ha266QtZXDE99BnKo....ABC

Переменные проще сохранить в файл и оттуда уже давать чекеру
Например, можно создать файл env.conf
Потом написать туда несколько строк типа
  NPL_LAB01_EXTERNAL_IP=12.15.63.124
  NPL_LAB01_WEB_PORT=8888
  NPL_STUDENT=herbie.hancock
  NPL_COHORT=DE99
  NPL_TOKEN=sk-npl-Ha266QtZXDE99BnKo....ABC

И потом подсунуть его докеру через --env-file env.conf
  docker run --rm -it --env-file env.conf {{.Image}}

А если есть подозрения, что не работает что-то с сетью, то может надо будет добавить
флаг --net=host в команду запуска (сразу после run), но скорее всего не понадобится

Напоминаем также, что при возникновении проблем следует обратиться к мануалу по дебагу вот тут:
{{.Debug}}
]]

confirm_display = {
    "STUDENT",
    "COHORT",
    { name = "TOKEN", masked = true },
    "LAB01_EXTERNAL_IP",
    { name = "LAB01_WEB_PORT", optional = true, default = "8000" },
}

analytics = {
    skip_tls = true,
    -- key = custom name, value = env var name (prefix added to env var)
    common_data = {
        NPL_LAB01_EXTERNAL_IP = "LAB01_EXTERNAL_IP",
        NPL_COHORT = "COHORT",
    },
    headers = {
        ["x-secret"] = "I know stuff, okay?",
        ["x-npl-lab"] = "01",
        ["x-npl-student"] = "env:STUDENT",
        ["Authorization"] = "Bearer env:TOKEN",
    },
}

-- The actual verification steps
-- These demonstrate the extensibility: HTTP checks, random path check, custom path check
checks = {
    {
        type = "http_get",
        name = "base_url_check",
        url = "http://{{.LAB01_EXTERNAL_IP}}:{{.LAB01_WEB_PORT}}",
        expected_status = 200,
        message_before = "Сначала проверю просто, что по адресу отвечает статусом OK",
        message_success = "Вроде тут ок 🎷🐍",
        on_failure = {
            message = "Проверка не обратилась успехом, ожидал статус 200 OK",
        },
    },
    {
        type = "http_get_random_path",
        name = "random_404_check",
        url = "http://{{.LAB01_EXTERNAL_IP}}:{{.LAB01_WEB_PORT}}",
        expected_status = 404,
        message_before = "Теперь проверяю, что рандомный адрес отвечает статусом 404 Not Found",
        message_success = "Всё как я и ожидаю, ура 🎷🐂",
        on_failure = {
            message = "Проверка не обратилась успехом, ожидал статус 404 Not Found",
        },
    },
    {
        type = "http_get",
        name = "student_path_check",
        url = "http://{{.LAB01_EXTERNAL_IP}}:{{.LAB01_WEB_PORT}}/{{.STUDENT}}-{{.COHORT}}",
        expected_status = 200,
        message_before = "Продолжаю. Теперь наконец проверяю персональный адрес",
        message_success = "Вроде тут тоже получилось 🎷🐊",
        on_failure = {
            message = "Проверка не обратилась успехом, ожидал статус 200 OK",
        },
    },
}

success_message = "Всё супер! Если видишь это сообщение, значит лаба сдана 🐩🐈🌭"
