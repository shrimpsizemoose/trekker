-- Lab 00: Simple parameter check
-- This Lua config compiles to a Go checker binary

lab = {
    id = "00",
    name = "Intro Lab",
    env_prefix = "NPL",  -- results in NPL_STUDENT, NPL_TOKEN, etc.
}

-- Required environment variables
required_env = {
    { name = "STUDENT",     error = "Мне надо знать, как тебя зовут" },
    { name = "TOKEN",       error = "Мне нужен токен, чтобы убедиться что ты это ты" },
    { name = "LAB00_PARAM", error = "параметр NPL_LAB00_PARAM не указан, а это практически единственная суть этой лабы, камон" },
}

-- Optional environment variables with defaults
optional_env = {
    -- { name = "DEBUG", default = "false", message = "использую режим по умолчанию" },
}

-- Usage help text (Go template syntax supported)
usage_text = [[
🤌 Чекер конфигурируется через переменные окружения

{{.EnvPrefix}}_STUDENT - ваше имя, как логин в ЛК (например herbie.hancock)
{{.EnvPrefix}}_TOKEN - ваш секретный токен, например, sk-npl-Ha266QtZXDE99BnKo....ABC
{{.EnvPrefix}}_LAB00_PARAM - параметр который надо указать как указано в задании

Переменные проще сохранить в файл и оттуда уже давать чекеру
Например, можно создать файл env.conf
Потом написать туда несколько строк типа
  NPL_STUDENT=john.doe
  NPL_TOKEN=sk-npl-Ha266QtZXDE99BnKo....ABC
  NPL_LAB00_PARAM=whateveryourpleasureimyourpunk

И потом подсунуть его докеру через --env-file env.conf
  docker run --rm -it --env-file env.conf {{.Image}}

А если есть подозрения, что не работает что-то с сетью, то может надо будет добавить
флаг --net=host в команду запуска (сразу после run), но скорее всего не понадобится

Напоминаем также, что при возникновении проблем следует обратиться к мануалу по дебагу вот тут:
{{.Debug}}
]]

-- Settings confirmation display
confirm_display = {
    "STUDENT",
    { name = "TOKEN", masked = true },
    "LAB00_PARAM",
}

-- Analytics configuration
analytics = {
    skip_tls = true,
    -- key = custom name, value = env var name (prefix added to env var)
    common_data = {
        labParam = "LAB00_PARAM",  -- "labParam": os.Getenv("NPL_LAB00_PARAM")
    },
    headers = {
        ["x-secret"] = "I know stuff, okay?",
        ["x-npl-lab"] = "00",
        ["x-npl-student"] = "env:STUDENT",
        ["Authorization"] = "Bearer env:TOKEN",
    },
}

-- The actual verification steps
checks = {
    {
        type = "param_equals",
        env_var = "LAB00_PARAM",
        expected = "dontyouevertrustmymercy",
        case_insensitive = true,
        on_failure = {
            event = "005_anecdote_settles_in_the_smear_of_this_corpse",
            message = "Параметр не совпадает с тем который должен быть, попробуй ещё раз",
        },
    },
}

-- Success message
success_message = "Кажется всё получилось, поздравляю! ✅ Если ты видишь это сообщение то лаба сдана! 😃"
