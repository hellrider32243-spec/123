import { useEffect, useState } from 'react'
import {
  motion,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
} from 'framer-motion'
import { arrivals, categories, orderChannels, store } from './data'
import './App.css'

const easeOut = [0.22, 1, 0.36, 1] as const

function App() {
  const reduceMotion = useReducedMotion()
  const [scrolled, setScrolled] = useState(false)
  const [activeCategory, setActiveCategory] = useState(0)
  const { scrollYProgress } = useScroll()
  const progress = useSpring(scrollYProgress, {
    stiffness: 120,
    damping: 28,
    mass: 0.35,
  })
  const heroY = useTransform(scrollYProgress, [0, 0.35], [0, 120])
  const heroScale = useTransform(scrollYProgress, [0, 0.35], [1, 1.12])

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    if (reduceMotion) return
    const id = window.setInterval(() => {
      setActiveCategory((prev) => (prev + 1) % categories.length)
    }, 4200)
    return () => window.clearInterval(id)
  }, [reduceMotion])

  return (
    <div className="page">
      <motion.div
        className="scroll-progress"
        style={{ scaleX: progress }}
        aria-hidden="true"
      />

      <header className={`nav${scrolled ? ' nav-scrolled' : ''}`}>
        <a className="nav-brand" href="#top" aria-label={`${store.brand} — на главную`}>
          <span className="nav-mark" aria-hidden="true" />
          {store.brand}
        </a>
        <nav className="nav-links" aria-label="Основная навигация">
          <a href="#privoz">Привоз</a>
          <a href="#assortiment">Ассортимент</a>
          <a href="#zakaz">Заказ</a>
          <a href="#magazin">Магазин</a>
        </nav>
        <a
          className="nav-cta"
          href={store.telegram}
          target="_blank"
          rel="noreferrer"
        >
          Telegram
        </a>
      </header>

      <main id="top">
        <section className="hero" aria-label="Главный экран">
          <motion.div className="hero-media" style={{ y: reduceMotion ? 0 : heroY }}>
            <motion.img
              src={store.heroImage}
              alt="Свежие фрукты и овощи на прилавке"
              style={{ scale: reduceMotion ? 1 : heroScale }}
              initial={reduceMotion ? false : { scale: 1.14, opacity: 0.65 }}
              animate={
                reduceMotion
                  ? { scale: 1, opacity: 1 }
                  : { scale: [1.14, 1.05, 1.1], opacity: 1 }
              }
              transition={
                reduceMotion
                  ? { duration: 0.8 }
                  : { duration: 18, ease: 'linear', repeat: Infinity, repeatType: 'mirror' }
              }
            />
            <div className="hero-shade" aria-hidden="true" />
            <div className="hero-glow" aria-hidden="true" />
          </motion.div>

          <div className="hero-content">
            <motion.p
              className="hero-brand"
              initial={reduceMotion ? false : { opacity: 0, y: 40, filter: 'blur(8px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
              transition={{ duration: 0.9, ease: easeOut }}
            >
              Фруктовый
              <br />
              дом
            </motion.p>
            <motion.h1
              initial={reduceMotion ? false : { opacity: 0, y: 28 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.75, delay: 0.15, ease: easeOut }}
            >
              Свежий привоз
              <br />
              каждый день
            </motion.h1>
            <motion.p
              className="hero-lead"
              initial={reduceMotion ? false : { opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.28, ease: easeOut }}
            >
              Фрукты и овощи в Черноголовке. Заказывайте в Telegram или
              заходите на Школьный бульвар, 10.
            </motion.p>
            <motion.div
              className="hero-actions"
              initial={reduceMotion ? false : { opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.4, ease: easeOut }}
            >
              <a
                className="btn btn-primary"
                href={store.telegram}
                target="_blank"
                rel="noreferrer"
              >
                <span>Заказать в Telegram</span>
              </a>
              <a className="btn btn-ghost" href="#magazin">
                Как добраться
              </a>
            </motion.div>
          </div>

          {!reduceMotion && (
            <motion.a
              className="hero-scroll"
              href="#privoz"
              aria-label="Листать ниже"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1, y: [0, 8, 0] }}
              transition={{
                opacity: { delay: 1, duration: 0.5 },
                y: { delay: 1, duration: 1.6, repeat: Infinity, ease: 'easeInOut' },
              }}
            >
              <span />
            </motion.a>
          )}
        </section>

        <section id="privoz" className="marquee-section" aria-label="Сегодня в привозе">
          <div className="marquee-label">Сегодня в привозе</div>
          <div className="marquee" aria-hidden="true">
            <div className={`marquee-track${reduceMotion ? ' is-static' : ''}`}>
              {[...arrivals, ...arrivals].map((item, index) => (
                <span key={`${item}-${index}`}>{item}</span>
              ))}
            </div>
          </div>
          <p className="marquee-note">
            Актуальные цены и фото — в{' '}
            <a href={store.telegram} target="_blank" rel="noreferrer">
              {store.telegramLabel}
            </a>
          </p>
        </section>

        <section id="assortiment" className="section assortment">
          <div className="section-head">
            <motion.h2
              initial={reduceMotion ? false : { opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.6 }}
              transition={{ duration: 0.55, ease: easeOut }}
            >
              Что привозим
            </motion.h2>
            <motion.p
              initial={reduceMotion ? false : { opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.6 }}
              transition={{ duration: 0.55, delay: 0.08, ease: easeOut }}
            >
              Наведите на категорию — покажем витрину. Или листайте сами.
            </motion.p>
          </div>

          <div className="showcase" role="list">
            {categories.map((item, index) => {
              const isActive = activeCategory === index
              return (
                <motion.button
                  key={item.name}
                  type="button"
                  role="listitem"
                  className={`showcase-panel${isActive ? ' is-active' : ''}`}
                  onMouseEnter={() => setActiveCategory(index)}
                  onFocus={() => setActiveCategory(index)}
                  onClick={() => setActiveCategory(index)}
                  initial={reduceMotion ? false : { opacity: 0, y: 40 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.3 }}
                  transition={{ duration: 0.55, delay: index * 0.06, ease: easeOut }}
                  aria-pressed={isActive}
                >
                  <img src={item.image} alt="" loading="lazy" />
                  <div className="showcase-copy">
                    <span className="showcase-index">0{index + 1}</span>
                    <h3>{item.name}</h3>
                    <p>{item.note}</p>
                  </div>
                </motion.button>
              )
            })}
          </div>
        </section>

        <section id="zakaz" className="section delivery">
          <div className="delivery-panel">
            <div className="section-head light">
              <motion.h2
                initial={reduceMotion ? false : { opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.55, ease: easeOut }}
              >
                Заказ за минуту
              </motion.h2>
              <motion.p
                initial={reduceMotion ? false : { opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.55, delay: 0.08, ease: easeOut }}
              >
                Напишите, что нужно — соберём заказ. Или оформите через сервис
                доставки.
              </motion.p>
            </div>
            <div className="delivery-list">
              {orderChannels.map((channel, index) => (
                <motion.a
                  key={channel.name}
                  className="delivery-link"
                  href={channel.href}
                  target={channel.external ? '_blank' : undefined}
                  rel={channel.external ? 'noreferrer' : undefined}
                  initial={reduceMotion ? false : { opacity: 0, x: -24 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true, amount: 0.5 }}
                  transition={{ duration: 0.45, delay: index * 0.07, ease: easeOut }}
                  whileHover={reduceMotion ? undefined : { x: 8 }}
                >
                  <span className="delivery-name">{channel.name}</span>
                  <span className="delivery-desc">{channel.desc}</span>
                  <span className="delivery-arrow" aria-hidden="true">
                    →
                  </span>
                </motion.a>
              ))}
            </div>
          </div>
        </section>

        <section id="magazin" className="section visit">
          <div className="visit-layout">
            <div className="visit-copy">
              <motion.h2
                initial={reduceMotion ? false : { opacity: 0, y: 22 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.55, ease: easeOut }}
              >
                Магазин в Черноголовке
              </motion.h2>
              <motion.p
                className="visit-lead"
                initial={reduceMotion ? false : { opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.55, delay: 0.08, ease: easeOut }}
              >
                Приходите сами за свежим привозом — или закажите заранее, и мы
                соберём к вашему приходу.
              </motion.p>
              <dl className="visit-facts">
                {[
                  ['Адрес', store.address],
                  ['Рядом', store.landmark],
                  ['Часы', store.hours],
                  ['Отзывы', store.rating],
                ].map(([label, value], index) => (
                  <motion.div
                    key={label}
                    initial={reduceMotion ? false : { opacity: 0, y: 12 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.4, delay: 0.1 + index * 0.06 }}
                  >
                    <dt>{label}</dt>
                    <dd>{value}</dd>
                  </motion.div>
                ))}
              </dl>
              <div className="visit-actions">
                <a className="btn btn-primary" href={store.phoneHref}>
                  {store.phoneDisplay}
                </a>
                <a
                  className="btn btn-secondary"
                  href={store.mapsUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  Открыть на карте
                </a>
              </div>
            </div>
            <motion.div
              className="visit-visual"
              initial={reduceMotion ? false : { opacity: 0, scale: 1.06 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true, amount: 0.35 }}
              transition={{ duration: 0.9, ease: easeOut }}
            >
              <img src={store.visitImage} alt="Яркие фрукты на витрине" loading="lazy" />
            </motion.div>
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="footer-brand">{store.brand}</div>
        <p>Фрукты и овощи · Черноголовка · {store.telegramLabel}</p>
        <div className="footer-links">
          <a href={store.telegram} target="_blank" rel="noreferrer">
            Telegram
          </a>
          <a href="#magazin">Контакты</a>
          <a href={store.phoneHref}>Телефон</a>
        </div>
      </footer>
    </div>
  )
}

export default App
