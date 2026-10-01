export const categories = [
  {
    name: 'Фрукты',
    note: 'Персики, киви, груши, яблоки, мандарины',
    image:
      'https://images.unsplash.com/photo-1619566636858-adf3ef46400b?auto=format&fit=crop&w=1200&q=80',
  },
  {
    name: 'Овощи и зелень',
    note: 'Хрустящие, свежие, каждый день с базы',
    image:
      'https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=1200&q=80',
  },
  {
    name: 'Ягоды и сухофрукты',
    note: 'Чернослив, инжир и сезонные ягоды',
    image:
      'https://images.unsplash.com/photo-1498557850523-fd3d118b962e?auto=format&fit=crop&w=1200&q=80',
  },
  {
    name: 'Сезонное',
    note: 'Дыни, новинки и то, что только привезли',
    image:
      'https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?auto=format&fit=crop&w=1200&q=80',
  },
] as const

export const arrivals = [
  'Яблоки Медовый хруст 250₽/кг',
  'Персики Крым 580₽/кг',
  'Киви 450₽/кг',
  'Груши 350₽/кг',
  'Дыня Торпедо 150₽/кг',
  'Мандарины 350₽/кг',
  'Чернослив Конфетка 250₽/кг',
  'Авокадо ХАС 140₽/шт',
] as const

export const orderChannels = [
  {
    name: 'Telegram',
    desc: '@FruitHome — цены, фото и заказ',
    href: 'https://t.me/FruitHome',
    external: true,
  },
  {
    name: 'Телефон',
    desc: '+7 (967) 079-47-17',
    href: 'tel:+79670794717',
    external: false,
  },
  {
    name: 'Яндекс Маркет',
    desc: 'Онлайн-заказ с доставкой',
    href: 'https://market.yandex.ru/',
    external: true,
  },
  {
    name: 'Купер',
    desc: 'Доставка продуктов на дом',
    href: 'https://kuper.ru/',
    external: true,
  },
] as const

export const store = {
  brand: 'Фруктовый дом',
  phoneDisplay: '+7 (967) 079-47-17',
  phoneHref: 'tel:+79670794717',
  telegram: 'https://t.me/FruitHome',
  telegramLabel: '@FruitHome',
  address: 'Черноголовка, Школьный бул., 10',
  hours: 'Ежедневно 10:00–22:00',
  landmark: 'ост. «Черноголовка», ~190 м',
  mapsUrl: 'https://yandex.ru/maps/org/fruktovy_dom/194204967960/',
  rating: '4.9 на Яндекс Картах',
  heroImage:
    'https://images.unsplash.com/photo-1488459716781-31db52582fe9?auto=format&fit=crop&w=2200&q=80',
  visitImage:
    'https://images.unsplash.com/photo-1610832958506-aa56368176cf?auto=format&fit=crop&w=1600&q=80',
}
