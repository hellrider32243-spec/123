import { motion, useReducedMotion } from 'framer-motion'
import { categories, store } from './data'
import './App.css'

const heroImage =
  'https://images.unsplash.com/photo-1488459716781-31db52582fe9?auto=format&fit=crop&w=2000&q=80'

const fadeUp = {
  hidden: { opacity: 0, y: 28 },
  show: { opacity: 1, y: 0 },
}

function App() {
  const reduceMotion = useReducedMotion()

  return (
    <div className="page">
      <header className="nav">
        <a className="nav-brand" href="#top" aria-label={`${store.brand} — на главную`}>
          {store.brand}
        </a>
        <nav className="nav-links" aria-label="Основная навигация">
          <a href="#assortiment">Ассортимент</a>
          <a href="#zakaz">Заказ</a>
          <a href="#magazin">Магазин</a>
        </nav>
        <a className="nav-cta" href={store.telegram} target="_blank" rel="noreferrer">
          Telegram
        </a>
      </header>

      <main id="top">
        <section className="hero" aria-label="Главный экран">
          <div className="hero-media">
            <motion.img
              src={heroImage}
              alt="Свежие фрукты и овощи на прилавке"
              initial={reduceMotion ? false : { scale: 1.08, opacity: 0.75 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 1.4, ease: [0.22, 1, 0.36, 1] }}
            />
            <div className="hero-shade" aria-hidden="true" />
          </div>

          <div className="hero-content">
            <motion.p
              className="hero-brand"
              variants={fadeUp}
              initial={reduceMotion ? false : 'hidden'}
              animate="show"
              transition={{ duration: 0.7, delay: 0.1 }}
            >
              Фруктовый
              <br />
              дом
            </motion.p>
            <motion.h1
              variants={fadeUp}
              initial={reduceMotion ? false : 'hidden'}
              animate="show"
              transition={{ duration: 0.75, delay: 0.22 }}
            >
              Свежий привоз
              <br />
              каждый день
            </motion.h1>
            <motion.p
              className="hero-lead"
              variants={fadeUp}
              initial={reduceMotion ? false : 'hidden'}
              animate="show"
              transition={{ duration: 0.7, delay: 0.34 }}
            >
              Фрукты и овощи в Черноголовке. Заказывайте в Telegram или
              заходите на Школьный бульвар, 10.
            </motion.p>
            <motion.div
              className="hero-actions"
              variants={fadeUp}
              initial={reduceMotion ? false : 'hidden'}
              animate="show"
              transition={{ duration: 0.7, delay: 0.46 }}
            >
              <a
                className="btn btn-primary"
                href={store.telegram}
                target="_blank"
                rel="noreferrer"
              >
                Заказать в Telegram
              </a>
              <a className="btn btn-ghost" href="#magazin">
                Как добраться
              </a>
            </motion.div>
          </div>
        </section>

        <section id="assortiment" className="section assortment">
          <div className="section-head">
            <h2>Что привозим</h2>
            <p>Следите за новинками и ценами в нашем Telegram.</p>
          </div>
          <div className="assortment-grid">
            {categories.map((item, index) => (
              <motion.article
                key={item.name}
                className="assortment-item"
                initial={reduceMotion ? false : { opacity: 0, y: 36 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.35 }}
                transition={{ duration: 0.55, delay: index * 0.08 }}
              >
                <div className="assortment-image">
                  <img src={item.image} alt={item.name} loading="lazy" />
                </div>
                <div className="assortment-copy">
                  <h3>{item.name}</h3>
                  <p>{item.note}</p>
                </div>
              </motion.article>
            ))}
          </div>
        </section>

        <section id="zakaz" className="section delivery">
          <div className="delivery-panel">
            <div className="section-head light">
              <h2>Заказ и доставка</h2>
              <p>
                Напишите в Telegram, что нужно — соберём заказ. Также можно
                позвонить или заказать через сервисы доставки.
              </p>
            </div>
            <div className="delivery-list">
              <a
                className="delivery-link"
                href={store.telegram}
                target="_blank"
                rel="noreferrer"
              >
                <span className="delivery-name">Telegram</span>
                <span className="delivery-desc">
                  {store.telegramLabel} — цены и заказ
                </span>
                <span className="delivery-arrow" aria-hidden="true">
                  →
                </span>
              </a>
              <a className="delivery-link" href={store.phoneHref}>
                <span className="delivery-name">Телефон</span>
                <span className="delivery-desc">{store.phoneDisplay}</span>
                <span className="delivery-arrow" aria-hidden="true">
                  →
                </span>
              </a>
              <a
                className="delivery-link"
                href="https://market.yandex.ru/"
                target="_blank"
                rel="noreferrer"
              >
                <span className="delivery-name">Яндекс Маркет</span>
                <span className="delivery-desc">Онлайн-заказ с доставкой</span>
                <span className="delivery-arrow" aria-hidden="true">
                  →
                </span>
              </a>
              <a
                className="delivery-link"
                href="https://kuper.ru/"
                target="_blank"
                rel="noreferrer"
              >
                <span className="delivery-name">Купер</span>
                <span className="delivery-desc">Доставка продуктов на дом</span>
                <span className="delivery-arrow" aria-hidden="true">
                  →
                </span>
              </a>
            </div>
          </div>
        </section>

        <section id="magazin" className="section visit">
          <div className="visit-layout">
            <div className="visit-copy">
              <h2>Магазин в Черноголовке</h2>
              <p className="visit-lead">
                Приходите сами за свежим привозом — или закажите заранее, и мы
                соберём к вашему приходу.
              </p>
              <dl className="visit-facts">
                <div>
                  <dt>Адрес</dt>
                  <dd>{store.address}</dd>
                </div>
                <div>
                  <dt>Рядом</dt>
                  <dd>{store.landmark}</dd>
                </div>
                <div>
                  <dt>Часы</dt>
                  <dd>{store.hours}</dd>
                </div>
                <div>
                  <dt>Отзывы</dt>
                  <dd>{store.rating}</dd>
                </div>
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
              initial={reduceMotion ? false : { opacity: 0, scale: 1.04 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            >
              <img
                src="https://images.unsplash.com/photo-1610832958506-aa56368176cf?auto=format&fit=crop&w=1400&q=80"
                alt="Яркие фрукты на витрине"
                loading="lazy"
              />
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
