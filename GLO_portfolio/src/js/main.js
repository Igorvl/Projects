new WOW().init();

var mySwiper = new Swiper('.swiper-container', {
    pagination: {
    // el: '.swiper-pagination',
    el: '.projects__tabs',
    type: 'bullets',
    bulletClass: 'projects__bullet',
    bulletActiveClass: 'projects__bullet-active',
    clickable: true,
  },
});