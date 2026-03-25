package main

import (
	"fmt"
	"math/rand"
	"os"
	"strings"
	"time"

	"github.com/shrimpsizemoose/trekker/cli"
	"github.com/shrimpsizemoose/trekker/env"
	"github.com/shrimpsizemoose/trekker/logger"
	"github.com/shrimpsizemoose/trekker/utils"
)

const (
	EnvStudent       = "STUDENT_ID"
	EnvToken         = "TOKEN"
	EnvParam         = "DEMO_PARAMETER"
	EnvParamOptional = "DEMO_PARAMETER_OPTIONAL"
)

func setupLabDemoUsage() {
	cli.SetupUsage(`🤌 Чекер конфигурируется через переменные окружения

STUDENT_ID - ваше имя, как в ведомости (например herbie.hancock)
TOKEN - ваш секретный токен, например, sk-Ha266QtZXDE99BnKo....ABC
DEMO_PARAMETER - параметр который надо указать
DEMO_PARAMETER_OPTIONAL - параметр который можно не указывать

Переменные проще сохранить в файл и оттуда уже давать чекеру
Например, можно создать файл env.conf
Потом написать туда несколько строк типа
  STUDENT=john.doe
  TOKEN=sk-Ha266QtZXDE99BnKo....ABC
  DEMO_PARAMETER=quidoloremipsumquiadolorsitametconsectetur

И потом подсунуть его докеру через --env-file env.conf
  docker run --rm -it --env-file env.conf ghcr.io/shrimpsizemoose/demo-trekker:1.0

А если есть подозрения, что не работает что-то с сетью, то может надо будет добавить
флаг --net=host в команду запуска (сразу после run), но скорее всего не понадобится

Напоминаем также, что при возникновении проблем следует обратиться к мануалу по дебагу вот тут:
--- в вашем хелпе тут будет ссылка ---`)
}

func confirmLabDemoSettings() {
	fmt.Printf(
		"Вот такие настройки я считал:\n%s=%s\n%s=%s\n%s=%s\n%s=%s\n",
		EnvStudent, os.Getenv(EnvStudent),
		EnvToken, utils.MaskToken(os.Getenv(EnvToken)),
		EnvParam, os.Getenv(EnvParam),
		EnvParamOptional, env.GetEnvOrDefault(EnvParamOptional, "optional parameter", ""),
	)

	fmt.Println("Продолжаю через 5 секунд...")
	time.Sleep(5 * time.Second)
}

func progressBar(total time.Duration, msg string) {
	const width = 50
	const steps = 100
	d := total / steps

	fmt.Println(msg)
	for i := 0; i <= steps; i++ {
		filled := i * width / steps
		bar := strings.Repeat("=", filled) + strings.Repeat("-", width-filled)
		fmt.Printf("\r[%s] %3d%%", bar, i)
		time.Sleep(d)
	}
	fmt.Print("\n")
}

var diceFaces = []rune{'⚀', '⚁', '⚂', '⚃', '⚄', '⚅'}

func rollDice() int {
	return rand.Intn(6) + 1
}

func strike(s string) string {
	term := os.Getenv("TERM")
	if term == "" || term == "dumb" || os.Getenv("NO_COLOR") != "" {
		return "~" + s + "~"
	}
	return "\x1b[9m" + s + "\x1b[0m"
}

func colorize(s string, color string) string {
	term := os.Getenv("TERM")
	if term == "" || term == "dumb" || os.Getenv("NO_COLOR") != "" {
		return s
	}
	colors := map[string]string{
		"red":     "\x1b[31m",
		"green":   "\x1b[32m",
		"yellow":  "\x1b[33m",
		"blue":    "\x1b[34m",
		"magenta": "\x1b[35m",
		"cyan":    "\x1b[36m",
		"bold":    "\x1b[1m",
	}
	if code, ok := colors[color]; ok {
		return code + s + "\x1b[0m"
	}
	return s
}

func showBanner() {
	banner := `
╔══════════════════════════════════════════════════╗
║         🎲  DEMO CHECKER v0.1.0  🎲              ║
║                                                  ║
║     ██████╗ ███████╗███╗   ███╗ ██████╗          ║
║     ██╔══██╗██╔════╝████╗ ████║██╔═══██╗         ║
║     ██║  ██║█████╗  ██╔████╔██║██║   ██║         ║
║     ██║  ██║██╔══╝  ██║╚██╔╝██║██║   ██║         ║
║     ██████╔╝███████╗██║ ╚═╝ ██║╚██████╔╝         ║
║     ╚═════╝ ╚══════╝╚═╝     ╚═╝ ╚═════╝          ║
╚══════════════════════════════════════════════════╝
`
	fmt.Println(banner)
}

func main() {
	setupLabDemoUsage()
	showBanner()

	env.LoadEnv()
	env.RequireEnv(map[string]string{
		EnvStudent: "Мне надо знать, как тебя зовут",
		EnvToken:   "Мне нужен токен, чтобы убедиться что ты это ты",
		EnvParam:   "Параметр DEMO_PARAMETER не указан",
	})

	confirmLabDemoSettings()

	shouldSleep := os.Getenv("DONT_RUSH_ME") != "please"

	// rand.Seed is unnecessary for Go 1.20+
	// rand.Seed(time.Now().UnixNano())

	// Track stages for summary
	stages := []struct {
		name   string
		status string
	}{
		{"Инициализация", "✅"},
		{"Kafka тест", "✅"},
		{"Postgres проверка", "✅"},
		{"Финальная проверка", "⏳"},
	}

	fmt.Println(colorize("[STAGE 1] Инициализация проверки...", "cyan"))
	logger.Info.Println("Тут какое-то шуршание-шубуршание...\nКуда-то ходим, стучимся, что-то собираем, проверяем...\nПодождём несколько секунд, сделаем вид, что работаем")
	if shouldSleep {
		time.Sleep(5 * time.Second)
		fmt.Println(colorize("[STAGE 2] Тестирование Kafka...", "yellow"))
		progressBar(3*time.Second, "🤖  Делаю вид, что шлю сообщения в Kafka...")
	} else {
		fmt.Println(colorize("[STAGE 2] Тестирование Kafka...", "yellow"))
		progressBar(0, "🤖  Делаю вид, что шлю сообщения в Kafka...")
	}

	// Simulate Kafka results
	fmt.Println("\n" + colorize("📨 Результаты отправки в Kafka:", "yellow"))
	fmt.Println(strings.Repeat("─", 50))
	fmt.Printf("Отправлено сообщений: %s\n", colorize("1000", "bold"))
	fmt.Printf("Успешно доставлено:   %s\n", colorize(fmt.Sprintf("%d", 997+rand.Intn(4)), "green"))
	fmt.Printf("Средняя задержка:     %sms\n", colorize(fmt.Sprintf("%d", 12+rand.Intn(8)), "bold"))
	fmt.Printf("Топик:                %s\n", colorize("student.events", "cyan"))
	fmt.Println(strings.Repeat("─", 50))

	if shouldSleep {
		fmt.Println(colorize("[STAGE 3] Проверка Postgres...", "yellow"))
		progressBar(2*time.Second, "🤖  Теперь прикидываюсь, что сравниваю агрегаты в Postgres...")
	} else {
		fmt.Println(colorize("[STAGE 3] Проверка Postgres...", "yellow"))
		progressBar(0, "🤖  Теперь прикидываюсь, что сравниваю агрегаты в Postgres...")
	}

	// Simulate Postgres results
	fmt.Println("\n" + colorize("📊 Результаты проверки Postgres:", "cyan"))
	fmt.Println(strings.Repeat("─", 60))

	// Generate random test data
	expectedRows := []struct {
		metric   string
		expected int
		actual   int
	}{
		{"total_events", 10000, 9998 + rand.Intn(5)},
		{"unique_users", 523, 520 + rand.Intn(7)},
		{"avg_response_time_ms", 45, 43 + rand.Intn(5)},
		{"error_rate_percent", 2, rand.Intn(4)},
	}

	fmt.Printf("%-25s %-12s %-12s %s\n", "Метрика", "Ожидалось", "Получено", "Статус")
	fmt.Println(strings.Repeat("─", 60))

	allGood := true
	for _, row := range expectedRows {
		status := "✅"
		statusColor := "green"
		diff := float64(row.actual-row.expected) / float64(row.expected) * 100
		if diff < -5 || diff > 5 {
			status = "⚠️"
			statusColor = "yellow"
			allGood = false
		}
		fmt.Printf("%-25s %-12d %-12d %s\n",
			row.metric,
			row.expected,
			row.actual,
			colorize(status, statusColor))
	}

	fmt.Println(strings.Repeat("─", 60))
	if allGood {
		fmt.Println(colorize("✓ Все метрики в пределах допустимых значений", "green"))
	} else {
		fmt.Println(colorize("⚠ Некоторые метрики отклоняются, но в допустимых пределах", "yellow"))
	}

	fmt.Println(colorize("[STAGE 4] Финальная проверка...", "magenta"))
	logger.Info.Printf("Теперь бросим кубик 🎲, и узнаем %s сдал ли ты лабу", strike("насколько ты везучий"))
	if shouldSleep {
		time.Sleep(3 * time.Second)
	}
	// Animate dice roll
	fmt.Print("🎲 Бросаем кубик: ")
	for range 50 {
		roll := rand.Intn(6)
		fmt.Printf("\r🎲 Бросаем кубик: %c (%d)", diceFaces[roll], roll+1)
		time.Sleep(200 * time.Millisecond)
	}

	n := rollDice()
	fmt.Printf("\r🎲 Бросаем кубик: %c [%d]\n\n", diceFaces[n-1], n)

	if n > 3 {
		fmt.Println(colorize("✅ УСПЕХ!", "green"))
		logger.Victory.Println("Поздравляю! Лаба сдана! 😃")
		stages[3].status = "✅"
	} else {
		fmt.Println(colorize("❌ НЕУДАЧА", "red"))
		logger.Error.Println("Не повезло! Тут ещё будет какой-то полезный комментарий (если повезет 😈)")
		stages[3].status = "❌"
	}

	// Print summary
	fmt.Println("\n" + colorize("═══════════════════════════════════════", "bold"))
	fmt.Println(colorize("📊 ИТОГОВЫЙ ОТЧЕТ", "bold"))
	fmt.Println(colorize("═══════════════════════════════════════", "bold"))
	for _, stage := range stages {
		fmt.Printf("%s %s\n", stage.status, stage.name)
	}
	fmt.Println(colorize("═══════════════════════════════════════", "bold"))

	if n > 3 {
		fmt.Println(colorize("🎉 Результат: ЛАБА ПРИНЯТА", "green"))
	} else {
		fmt.Println(colorize("💔 Результат: ПОПРОБУЙТЕ ЕЩЁ РАЗ", "red"))
	}
}
