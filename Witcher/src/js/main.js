var mySwiper = new Swiper('.swiper-container', {
  speed: 400,
  slidesPerView: 1,
  loop: true,
  navigation: {
    nextEl: '.swiper-button-next',
  },
  // Responsive breakpoints
  breakpoints: {
    // when window width is <= 670px
    670: {
      slidesPerView: 2,
      spaceBetween: 30,
    },
  }
});

const menuButton = document.querySelector('.mobile-menu')
const menu = document.querySelector('.header')

menuButton.addEventListener('click', (param)=>{
  menu.classList.toggle('header__active')
})